"""
Excel Operation Tools — Called by SpreadsheetAgent, executed by frontend.

Each tool queues an operation that gets streamed to the Office.js frontend
via SSE. The frontend executes it against the live workbook.

The agent calls these tools incrementally (one at a time), seeing results
between calls — like Endex/Microsoft Agent Mode. No more "big bang" JSON plans.

Uses contextvars so each request has its own isolated operation queue.

Following CODING_RULES.md: KISS, no hardcoding.
Following NASA Power of 10: bounded inputs, check returns.
"""

from agents import function_tool
from typing import List, Optional, Dict, Any, Union
import contextvars
import asyncio
import json
import logging
import uuid

logger = logging.getLogger(__name__)


class OperationDeniedByUser(Exception):
    """Raised when the user denies a write operation in 'ask before edits' mode."""
    pass


def _sanitize_optional_int(value: Union[int, str, None]) -> Optional[int]:
    """Sanitize optional int params - LLMs sometimes pass 'null' as string."""
    if value is None or value == "null" or value == "":
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _sanitize_optional_str(value: Optional[str]) -> Optional[str]:
    """Sanitize optional str params - LLMs sometimes pass 'null' as string."""
    if value is None or value == "null" or value == "":
        return None
    return value

# ── Context-var operation queue (one per request) ──
_op_queue: contextvars.ContextVar[Optional[asyncio.Queue]] = contextvars.ContextVar(
    "excel_op_queue", default=None
)


def set_op_queue(q: asyncio.Queue) -> None:
    """Set the operation queue for the current async context."""
    _op_queue.set(q)


async def _emit(op: Dict[str, Any]) -> None:
    """Push an operation to the queue. Blocks for approval when mode is 'ask' and action is a write.

    Skips the per-op approval gate when ``_tool_pre_approved`` is True
    (set by ``_request_tool_approval`` for composite tools).

    Raises OperationDeniedByUser if the user denies the operation.
    """
    q = _op_queue.get(None)
    if not q:
        return

    # Include call_id for frontend correlation with tool calls (FIFO queue)
    # Only pop for write operations that need approval
    action = op.get("action", "")
    if action not in _READ_ONLY_ACTIONS:
        call_id = get_current_call_id()  # pops from queue
    else:
        call_id = peek_current_call_id()  # peek only for reads
    if call_id:
        op["call_id"] = call_id

    # Get approval mode from request-scoped dict (ContextVars don't propagate to SDK tool tasks)
    request_id = _current_request_id.get(None)
    mode = _edit_approval_mode_by_request.get(request_id, "accept") if request_id else _edit_approval_mode.get("accept")
    action = op.get("action", "")

    if mode == "ask" and action not in _READ_ONLY_ACTIONS and action not in _AUTO_APPROVED_ACTIONS:
        if _tool_pre_approved.get(False):
            await q.put(op)
            return

        approval_id = str(uuid.uuid4())
        op["approval_id"] = approval_id

        request_id = _current_request_id.get(None)
        if request_id and request_id in _pending_approvals_by_request:
            loop = asyncio.get_event_loop()
            future: asyncio.Future = loop.create_future()
            _pending_approvals_by_request[request_id][approval_id] = future

            await q.put(op)
            result = await future  # No timeout - wait indefinitely for user response

            if not result.get("approved", True):
                sheet = op.get("sheet") or op.get("name", "")
                raise OperationDeniedByUser(
                    f"Operation denied by user: {action.replace('_', ' ')}"
                    + (f" on {sheet}" if sheet else "")
                )
            return

    await q.put(op)


# ── Module-level pending reads registry (shared across requests) ──
# Used by excel_read_range to wait for frontend response.
# Keyed by request_id so /read-response endpoint can resolve reads from different HTTP context.
_pending_reads_by_request: Dict[str, Dict[str, asyncio.Future]] = {}
_pending_reads_lock = asyncio.Lock()

# ContextVar to track current request_id within agent execution context
_current_request_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "excel_current_request_id", default=None
)

# Per-request call_id QUEUE tracking (ContextVars don't propagate to SDK tool tasks)
# Uses deque for FIFO ordering - tool_call events arrive before tools execute
from collections import deque
_call_id_queue_by_request: Dict[str, deque] = {}

# Read-only tools that don't need call_id correlation (they don't emit write operations)
_READ_ONLY_TOOLS = frozenset({
    "excel_get_workbook_structure", "excel_get_sheet_summary", "excel_read_range",
    "excel_find_columns_by_header", "excel_activate_sheet",
})


def set_current_call_id(call_id: Optional[str], request_id: Optional[str] = None, tool_name: Optional[str] = None) -> None:
    """Enqueue a call_id for tool-operation correlation (FIFO). Only for Excel write tools."""
    # Only enqueue for Excel tools that emit write operations
    # Skip: read-only Excel tools, MCP tools, valuation tools, etc.
    if not tool_name or not tool_name.startswith("excel_"):
        return  # Not an Excel tool - don't enqueue
    if tool_name in _READ_ONLY_TOOLS:
        return  # Read-only Excel tool - don't enqueue
    rid = request_id or _current_request_id.get(None)
    if rid and call_id:
        if rid not in _call_id_queue_by_request:
            _call_id_queue_by_request[rid] = deque()
        _call_id_queue_by_request[rid].append(call_id)


def get_current_call_id() -> Optional[str]:
    """Dequeue and return the next call_id for the current request (FIFO)."""
    request_id = _current_request_id.get(None)
    if request_id and request_id in _call_id_queue_by_request:
        q = _call_id_queue_by_request[request_id]
        if q:
            return q.popleft()
    return None


def peek_current_call_id() -> Optional[str]:
    """Peek at the next call_id without removing it (for read-only operations)."""
    request_id = _current_request_id.get(None)
    if request_id and request_id in _call_id_queue_by_request:
        q = _call_id_queue_by_request[request_id]
        if q:
            return q[0]
    return None


def init_pending_reads(request_id: str) -> None:
    """Initialize pending reads for a request. Called at start of agent execution."""
    _current_request_id.set(request_id)
    _pending_reads_by_request[request_id] = {}


def get_pending_reads() -> Optional[Dict[str, asyncio.Future]]:
    """Get pending reads dict for current request context."""
    request_id = _current_request_id.get(None)
    if request_id:
        return _pending_reads_by_request.get(request_id)
    return None


async def resolve_pending_read(request_id: str, read_id: str, data: Dict[str, Any]) -> bool:
    """Resolve a pending read with data from frontend. Returns True if found.
    
    Called from /read-response endpoint (different HTTP context than agent execution).
    Uses request_id to find the correct pending reads registry.
    """
    reads = _pending_reads_by_request.get(request_id)
    if reads and read_id in reads:
        future = reads.pop(read_id)
        if not future.done():
            future.set_result(data)
        return True
    return False


def cancel_all_pending_reads(request_id: str) -> None:
    """Cancel all pending reads for a request. Called on stream cancellation."""
    reads = _pending_reads_by_request.get(request_id)
    if reads:
        for rid, future in list(reads.items()):
            if not future.done():
                future.cancel()
        reads.clear()


def cleanup_pending_reads(request_id: str) -> None:
    """Remove pending reads registry for a request. Called after agent completes."""
    _pending_reads_by_request.pop(request_id, None)


# ── Module-level pending approvals registry (mirrors reads pattern) ──
_pending_approvals_by_request: Dict[str, Dict[str, asyncio.Future]] = {}

# Store approval mode per-request (NOT ContextVar - those don't propagate to SDK tool calls)
_edit_approval_mode_by_request: Dict[str, str] = {}

_edit_approval_mode: contextvars.ContextVar[str] = contextvars.ContextVar(
    "excel_edit_approval_mode", default="accept"
)

_READ_ONLY_ACTIONS = frozenset({
    "read_range", "get_workbook_structure", "get_sheet_summary",
    "find_columns_by_header", "activate_sheet",
})

_AUTO_APPROVED_ACTIONS = frozenset({
    "format_range",
    "add_conditional_format",
    "autofit_columns",
})

_tool_pre_approved: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "excel_tool_pre_approved", default=False
)


async def _request_tool_approval(description: str) -> None:
    """Request a single approval covering an entire composite tool's writes.

    Emits a synthetic ``tool_approval_request`` op and blocks until the
    frontend responds.  On approval sets ``_tool_pre_approved`` so subsequent
    ``_emit`` calls inside the same tool skip the per-op gate.

    Raises ``OperationDeniedByUser`` if the user denies.
    """
    # Get approval mode from request-scoped dict (ContextVars don't propagate to SDK tool tasks)
    request_id = _current_request_id.get(None)
    mode = _edit_approval_mode_by_request.get(request_id, "accept") if request_id else _edit_approval_mode.get("accept")
    if mode != "ask":
        return

    q = _op_queue.get(None)
    if not q:
        return

    request_id = _current_request_id.get(None)
    if not request_id or request_id not in _pending_approvals_by_request:
        return

    approval_id = str(uuid.uuid4())
    op: Dict[str, Any] = {
        "action": "tool_approval_request",
        "description": description,
        "approval_id": approval_id,
    }

    loop = asyncio.get_event_loop()
    future: asyncio.Future = loop.create_future()
    _pending_approvals_by_request[request_id][approval_id] = future

    await q.put(op)
    result = await future  # No timeout - wait indefinitely for user response

    if not result.get("approved", True):
        raise OperationDeniedByUser(f"Operation denied by user: {description}")

    _tool_pre_approved.set(True)


def init_pending_approvals(request_id: str, mode: str) -> None:
    """Initialize approval registry for a request. Called at start of agent execution."""
    _edit_approval_mode.set(mode)
    _edit_approval_mode_by_request[request_id] = mode  # Store in dict for cross-task access
    _pending_approvals_by_request[request_id] = {}


async def resolve_pending_approval(request_id: str, approval_id: str, approved: bool) -> bool:
    """Resolve a pending approval from frontend. Returns True if found."""
    approvals = _pending_approvals_by_request.get(request_id)
    if approvals and approval_id in approvals:
        future = approvals.pop(approval_id)
        if not future.done():
            future.set_result({"approved": approved})
        return True
    return False


def cancel_all_pending_approvals(request_id: str) -> None:
    """Cancel all pending approvals for a request. Called on stream cancellation."""
    approvals = _pending_approvals_by_request.get(request_id)
    if approvals:
        for aid, future in list(approvals.items()):
            if not future.done():
                future.cancel()
        approvals.clear()


def cleanup_pending_approvals(request_id: str) -> None:
    """Remove approval registry for a request. Called after agent completes."""
    _pending_approvals_by_request.pop(request_id, None)
    _edit_approval_mode_by_request.pop(request_id, None)


# ═══════════════════════════════════════════════════════════════════════════════
# Sheet Management
# ═══════════════════════════════════════════════════════════════════════════════


async def _create_sheet_confirmed(name: str, timeout: float = 15.0) -> str:
    """Internal bidirectional create-sheet. Waits for frontend confirmation.

    Returns a success or error string. Reuses the pending-reads Future
    infrastructure so no new API endpoints are needed.
    """
    reads = get_pending_reads()
    if reads is None:
        # Fallback: fire-and-forget if read context not initialized
        await _emit({"action": "create_sheet", "name": name})
        return f"Queued sheet creation: '{name}'."

    op_id = str(uuid.uuid4())
    loop = asyncio.get_event_loop()
    future: asyncio.Future = loop.create_future()
    reads[op_id] = future

    await _emit({"action": "create_sheet", "name": name, "read_id": op_id})

    try:
        result = await asyncio.wait_for(future, timeout=timeout)
        if result.get("success"):
            return f"Sheet '{name}' created successfully."
        else:
            error = result.get("error", "Unknown error")
            return f"Error creating sheet '{name}': {error}"
    except asyncio.TimeoutError:
        reads.pop(op_id, None)
        return f"Error: Sheet creation timed out after {timeout}s for '{name}'."
    except asyncio.CancelledError:
        reads.pop(op_id, None)
        return "Error: Sheet creation cancelled."


@function_tool
async def excel_create_sheet(name: str) -> str:
    """Create a new worksheet in the workbook. Safe if sheet already exists."""
    return await _create_sheet_confirmed(name)


@function_tool
async def excel_rename_sheet(old_name: str, new_name: str) -> str:
    """Rename an existing worksheet."""
    reads = get_pending_reads()
    if reads is None:
        await _emit({"action": "rename_sheet", "old_name": old_name, "new_name": new_name})
        return f"Sheet renamed: '{old_name}' → '{new_name}'."

    op_id = str(uuid.uuid4())
    loop = asyncio.get_event_loop()
    future: asyncio.Future = loop.create_future()
    reads[op_id] = future

    await _emit({"action": "rename_sheet", "old_name": old_name, "new_name": new_name, "read_id": op_id})

    try:
        result = await asyncio.wait_for(future, timeout=15.0)
        if result.get("success"):
            return f"Sheet renamed: '{old_name}' → '{new_name}'."
        else:
            error = result.get("error", "Unknown error")
            return f"Error renaming sheet '{old_name}' to '{new_name}': {error}"
    except asyncio.TimeoutError:
        reads.pop(op_id, None)
        return f"Error: Sheet rename timed out for '{old_name}' → '{new_name}'."
    except asyncio.CancelledError:
        reads.pop(op_id, None)
        return "Error: Sheet rename cancelled."


# ═══════════════════════════════════════════════════════════════════════════════
# Write Cells
# ═══════════════════════════════════════════════════════════════════════════════


@function_tool
async def excel_write_values(
    sheet: str,
    range: str,
    values_json: str,
    bold: bool = False,
    fill: Optional[str] = None,
    font_color: Optional[str] = None,
    font_size: Optional[str] = None,
    number_format: Optional[str] = None,
    horizontal_alignment: Optional[str] = None,
    border_bottom: Optional[str] = None,
    border_top: Optional[str] = None,
    merge: bool = False,
) -> str:
    """Write literal values to cells. Use this for fetched data, headers, labels.

    Args:
        sheet: Target worksheet name.
        range: A1 notation (e.g. "A1:G1" or "B2").
        values_json: JSON string of a 2D array matching range dimensions.
                     Example: '[["AAPL", "Apple", 3540000000000, 33.2]]'
                     Row-major: each inner array is one row.
        bold: Make text bold.
        fill: Background color hex (e.g. "#1F4E79").
        font_color: Font color hex.
        font_size: Font size in points (as string or int).
        number_format: Excel number format string (e.g. "#,##0", "0.0%", "0.0x").
        horizontal_alignment: "left", "center", or "right".
        border_bottom: Border style for bottom edge: "thin", "medium", "thick".
        border_top: Border style for top edge.
        merge: Merge all cells in the range into one.
    """
    # Sanitize optional params that LLMs sometimes pass as 'null' string
    fill = _sanitize_optional_str(fill)
    font_color = _sanitize_optional_str(font_color)
    font_size_int = _sanitize_optional_int(font_size)
    number_format = _sanitize_optional_str(number_format)
    horizontal_alignment = _sanitize_optional_str(horizontal_alignment)
    border_bottom = _sanitize_optional_str(border_bottom)
    border_top = _sanitize_optional_str(border_top)
    
    try:
        values = json.loads(values_json)
    except (json.JSONDecodeError, TypeError):
        return f"Error: values_json is not valid JSON: {values_json[:100]}"

    if not isinstance(values, list) or not values:
        return "Error: values_json must be a non-empty 2D array."

    # Ensure 2D
    if not isinstance(values[0], list):
        values = [values]

    # Safeguard: Detect format strings accidentally passed as values
    FORMAT_PATTERNS = {"#,##0", "0.00%", "0.0%", "$#,##0", "#,##0.00", "0.00", "0.0x", "yyyy-mm-dd", "mm/dd/yyyy"}
    detected_format = None
    for row in values:
        for val in row:
            if isinstance(val, str) and val in FORMAT_PATTERNS:
                detected_format = val
                break
        if detected_format:
            break
    if detected_format:
        return (
            f"Error: '{detected_format}' looks like a number format string, not a cell value. "
            f"Use the number_format parameter instead: excel_write_values(..., number_format=\"{detected_format}\") "
            f"or use excel_format_range() to apply formatting after writing values."
        )

    fmt: Dict[str, Any] = {}
    if bold:
        fmt["bold"] = True
    if fill:
        fmt["fill"] = fill
    if font_color:
        fmt["font_color"] = font_color
    if font_size_int:
        fmt["font_size"] = font_size_int
    if number_format:
        fmt["number_format"] = number_format
    if horizontal_alignment:
        fmt["horizontal_alignment"] = horizontal_alignment
    borders: Dict[str, Any] = {}
    if border_bottom:
        borders["bottom"] = {"style": border_bottom}
    if border_top:
        borders["top"] = {"style": border_top}
    if borders:
        fmt["borders"] = borders

    op: Dict[str, Any] = {
        "range": range,
        "values": values,
    }
    if merge:
        op["merge"] = True
    if fmt:
        op["format"] = fmt

    await _emit({
        "action": "write_cells",
        "sheet": sheet,
        "operations": [op],
    })

    rows = len(values)
    cols = len(values[0]) if values else 0
    fmt_note = " (with formatting)" if fmt else ""
    return f"Queued {rows}x{cols} values to {sheet}!{range}{fmt_note}."


def _expand_formula_template(spec: dict) -> Union[list, str]:
    """Expand a compact formula template into a full 2D formula array.

    Supports two modes:
    1. Matrix mode (row_var + col_var): produces NxN grid with optional diagonal.
    2. Column mode (row_var only): produces Nx1 column (or NxM if template is a list).

    Returns the 2D array, or an error string.
    """
    template = spec.get("template")
    if not template:
        return "Error: template object requires a 'template' field."

    row_var = spec.get("row_var", "r")
    row_values = spec.get("row_values")
    if not row_values or not isinstance(row_values, list):
        return "Error: template object requires a non-empty 'row_values' list."

    col_var = spec.get("col_var")
    col_values = spec.get("col_values")
    diagonal = spec.get("diagonal")

    # ── Matrix mode: row_var × col_var ──
    if col_var and col_values:
        result = []
        for rv in row_values:
            row = []
            for cv in col_values:
                if diagonal is not None and rv == cv:
                    diag = diagonal.replace(f"{{{row_var}}}", str(rv))
                    if col_var:
                        diag = diag.replace(f"{{{col_var}}}", str(cv))
                    row.append(diag)
                else:
                    cell = template.replace(f"{{{row_var}}}", str(rv))
                    cell = cell.replace(f"{{{col_var}}}", str(cv))
                    row.append(cell)
            result.append(row)
        return result

    # ── Column mode: row_var only ──
    if isinstance(template, list):
        # template is a list of formulas per column
        result = []
        for rv in row_values:
            row = [t.replace(f"{{{row_var}}}", str(rv)) for t in template]
            result.append(row)
        return result

    # Single-column
    return [[template.replace(f"{{{row_var}}}", str(rv))] for rv in row_values]


@function_tool
async def excel_write_formulas(
    sheet: str,
    range: str,
    formulas_json: str,
    bold: bool = False,
    number_format: Optional[str] = None,
    border_top: Optional[str] = None,
) -> str:
    """Write Excel formulas to cells. Use for derived calculations (SUM, AVERAGE, etc.).

    Args:
        sheet: Target worksheet name.
        range: A1 notation.
        formulas_json: JSON string — either:
            (a) A 2D array of formula strings:
                '[["=SUM(B2:B10)", "=AVERAGE(C2:C10)"]]'
                Use null for cells to skip.
            (b) A template object for large grids (>5×5). The server expands
                the template so the LLM doesn't need to emit thousands of
                repeated formulas. Structure:
                '{
                    "template": "=CORREL(Sheet1!{r}$2:{r}$100, Sheet1!{c}$2:{c}$100)",
                    "row_var": "r",
                    "col_var": "c",
                    "row_values": ["B","C","D"],
                    "col_values": ["B","C","D"],
                    "diagonal": "=1"
                }'
                - template: formula with {row_var} and {col_var} placeholders.
                - row_values / col_values: substitution lists (one per row/col).
                - diagonal (optional): formula or value for cells where row==col.
                - Same-axis templates (only row_var, no col_var) also supported:
                  row_values drives rows, each row gets the template with {row_var}
                  replaced. Result is Nx1 column (or NxM if template is a list).
        bold: Make text bold (for totals rows).
        number_format: Excel number format string.
        border_top: Border on top (e.g. "medium" for totals separator).
    """
    try:
        parsed = json.loads(formulas_json)
    except (json.JSONDecodeError, TypeError):
        return f"Error: formulas_json is not valid JSON: {formulas_json[:100]}"

    # ── Template expansion ──────────────────────────────────────────────
    if isinstance(parsed, dict) and "template" in parsed:
        expanded = _expand_formula_template(parsed)
        if isinstance(expanded, str):  # error message
            return expanded
        formulas = expanded
    else:
        formulas = parsed

    if not isinstance(formulas, list) or not formulas:
        return "Error: formulas_json must be a non-empty 2D array or template object."

    # Ensure 2D
    if not isinstance(formulas[0], list):
        formulas = [formulas]

    # Dimension check: warn if formula rows don't match target range rows
    import re as _re
    range_match = _re.match(r"^[A-Z]+(\d+):[A-Z]+(\d+)$", range, _re.IGNORECASE)
    if range_match:
        target_rows = int(range_match.group(2)) - int(range_match.group(1)) + 1
        formula_rows = len(formulas)
        if formula_rows < target_rows and formula_rows <= 2:
            return (
                f"Error: formulas_json has {formula_rows} row(s) but target range "
                f"{range} spans {target_rows} rows. Write formulas to a small range "
                f"(e.g. 1-2 rows) then use excel_copy_range with dest_end_cell to "
                f"fill down efficiently."
            )

    fmt: Dict[str, Any] = {}
    if bold:
        fmt["bold"] = True
    if number_format:
        fmt["number_format"] = number_format
    if border_top:
        fmt["borders"] = {"top": {"style": border_top}}

    cell_op: Dict[str, Any] = {"range": range, "formulas": formulas}
    if fmt:
        cell_op["format"] = fmt

    rows = len(formulas)
    cols = len(formulas[0]) if formulas else 0
    fmt_note = " (with formatting)" if fmt else ""

    emit_op: Dict[str, Any] = {
        "action": "write_cells",
        "sheet": sheet,
        "operations": [cell_op],
    }

    # Use confirmed (bidirectional) write when pending_reads is available
    reads = get_pending_reads()
    if reads is not None:
        op_id = str(uuid.uuid4())
        loop = asyncio.get_event_loop()
        future: asyncio.Future = loop.create_future()
        reads[op_id] = future
        emit_op["read_id"] = op_id
        await _emit(emit_op)

        try:
            result = await asyncio.wait_for(future, timeout=30.0)
            if result.get("success"):
                return f"Written {rows}x{cols} formulas to {sheet}!{range}{fmt_note} (confirmed)."
            else:
                error = result.get("error", "Unknown error")
                return f"Error writing formulas to {sheet}!{range}: {error}"
        except asyncio.TimeoutError:
            reads.pop(op_id, None)
            return f"WARNING: Write formulas to {sheet}!{range} timed out — may not have executed."
        except asyncio.CancelledError:
            reads.pop(op_id, None)
            return "Error: Write formulas cancelled."

    # Fallback: fire-and-forget when pending_reads is not available
    await _emit(emit_op)
    return f"Queued {rows}x{cols} formulas to {sheet}!{range}{fmt_note}."


# ═══════════════════════════════════════════════════════════════════════════════
# Reading (Bidirectional - waits for frontend response)
# ═══════════════════════════════════════════════════════════════════════════════


def _parse_range_dimensions(range_str: str) -> tuple[int, int]:
    """Parse A1 notation range and return (rows, cols). Returns (0, 0) on parse error."""
    import re
    match = re.match(r'^([A-Z]+)(\d+):([A-Z]+)(\d+)$', range_str.upper())
    if not match:
        match_single = re.match(r'^([A-Z]+)(\d+)$', range_str.upper())
        if match_single:
            return (1, 1)
        return (0, 0)

    start_col, start_row, end_col, end_row = match.groups()

    def col_to_num(col: str) -> int:
        num = 0
        for c in col:
            num = num * 26 + (ord(c) - ord('A') + 1)
        return num

    rows = int(end_row) - int(start_row) + 1
    cols = col_to_num(end_col) - col_to_num(start_col) + 1
    return (rows, cols)


def _parse_range_start(range_str: str) -> tuple[int, str]:
    """Parse A1 notation range and return (start_row, start_col). Returns (0, '') on error."""
    import re
    match = re.match(r'^([A-Z]+)(\d+)', range_str.upper())
    if match:
        return int(match.group(2)), match.group(1)
    return 0, ''


@function_tool
async def excel_read_range(
    sheet: str,
    range: str,
    include_formulas: bool = True,
    timeout_seconds: float = 30.0,
) -> str:
    """Read cell values (and optionally formulas) from a range. Use to verify data before writing cross-sheet formulas.

    WHEN TO USE:
    - Before writing formulas that reference another sheet you just modified
    - To verify row/column positions of labels after writing data
    - To check current cell contents before overwriting

    Args:
        sheet: Worksheet name to read from.
        range: A1 notation (e.g., "A1:G12", "A1:A20"). Max 100 rows x 50 columns.
        include_formulas: If True, also return formulas. Default True.
        timeout_seconds: Max wait time for Excel response. Default 30s.

    Returns:
        JSON string with:
        - "values": 2D array of raw cell values (use these for writing back)
        - "display_values": 2D array of formatted cell text (what the user sees in Excel).
          Use display_values to understand the data — e.g., "3:30 PM" instead of 0.645833.
          If a user references "3:30 PM", match it against display_values, not values.
        - "formulas": 2D array of cell formulas (if include_formulas=True)
        - "rows": number of rows returned
        - "cols": number of columns returned
        - "row_numbers": array mapping each index to its Excel row number.
          values[i] is Excel row row_numbers[i]. Use row_numbers to write back to the correct row.
        - "start_col": the starting column letter (e.g., "B")
        On error: "Error: <message>"

    Example:
        result = excel_read_range("Schedule", "B2:I14")
        # display_values[9][0] = "3:30 PM", row_numbers[9] = 11 → write to C11:I11
        # If user says "move X to 12 PM" but "12:00 PM" is not in display_values → tell user
    """
    MAX_ROWS = 100
    MAX_COLS = 50
    
    rows, cols = _parse_range_dimensions(range)
    if rows == 0 or cols == 0:
        return f"Error: Invalid range format '{range}'. Use A1 notation (e.g., 'A1:G12')."
    if rows > MAX_ROWS or cols > MAX_COLS:
        return f"Error: Range too large ({rows}x{cols}). Max is {MAX_ROWS} rows x {MAX_COLS} columns."
    
    reads = get_pending_reads()
    if reads is None:
        return "Error: Read context not initialized. Internal error."
    
    read_id = str(uuid.uuid4())
    loop = asyncio.get_event_loop()
    future: asyncio.Future = loop.create_future()
    reads[read_id] = future
    
    await _emit({
        "action": "read_range",
        "sheet": sheet,
        "range": range,
        "read_id": read_id,
        "include_formulas": include_formulas,
    })
    
    try:
        result = await asyncio.wait_for(future, timeout=timeout_seconds)
        if result.get("success"):
            data = result.get("data", {})
            values = data.get("values", [])
            formulas = data.get("formulas", []) if include_formulas else []
            display_values = data.get("display_values", [])
            start_row, start_col = _parse_range_start(range)
            num_rows = len(values)
            result_dict = {
                "values": values,
                "formulas": formulas,
                "rows": num_rows,
                "cols": len(values[0]) if values and num_rows > 0 else 0,
            }
            if display_values:
                result_dict["display_values"] = display_values
            if start_row:
                result_dict["row_numbers"] = [start_row + i for i, _ in enumerate(values)]
            if start_col:
                result_dict["start_col"] = start_col
            return json.dumps(result_dict)
        else:
            error_msg = result.get("error", "Unknown read error")
            return f"Error: {error_msg}"
    except asyncio.TimeoutError:
        reads.pop(read_id, None)
        return f"Error: Read timed out after {timeout_seconds}s. Sheet '{sheet}' range '{range}' may not exist."
    except asyncio.CancelledError:
        reads.pop(read_id, None)
        return "Error: Read cancelled."
    except Exception as e:
        reads.pop(read_id, None)
        logger.exception(f"excel_read_range failed: {e}")
        return f"Error: Read failed: {str(e)}"


# ═══════════════════════════════════════════════════════════════════════════════
# Workbook Discovery (Tool-First Architecture)
# ═══════════════════════════════════════════════════════════════════════════════


@function_tool
async def excel_get_workbook_structure(timeout_seconds: float = 30.0) -> str:
    """Get overview of entire workbook - sheets, dimensions, and headers.

    Call this FIRST to understand workbook structure before reading specific data.
    This is the preferred way to explore an unfamiliar workbook.

    Args:
        timeout_seconds: Max wait time for Excel response. Default 30s.

    Returns:
        JSON: {
            "sheets": [
                {"name": "KIRALAR", "rows": 40, "cols": 6,
                 "headers": ["", "date", "location", "amount", "currency", "ILS/TRY"],
                 "used_range": "A1:F40"},
                ...
            ]
        }

    Example:
        # First call to understand what sheets exist
        result = excel_get_workbook_structure()
        # Returns all sheets with their headers — use this to plan your work
    """
    reads = get_pending_reads()
    if reads is None:
        return "Error: Read context not initialized. Internal error."

    read_id = str(uuid.uuid4())
    loop = asyncio.get_event_loop()
    future: asyncio.Future = loop.create_future()
    reads[read_id] = future

    await _emit({
        "action": "get_workbook_structure",
        "read_id": read_id,
    })

    try:
        result = await asyncio.wait_for(future, timeout=timeout_seconds)
        if result.get("success"):
            return json.dumps(result.get("data", {}))
        else:
            return f"Error: {result.get('error', 'Unknown error')}"
    except asyncio.TimeoutError:
        reads.pop(read_id, None)
        return f"Error: Workbook structure read timed out after {timeout_seconds}s."
    except asyncio.CancelledError:
        reads.pop(read_id, None)
        return "Error: Read cancelled."
    except Exception as e:
        reads.pop(read_id, None)
        logger.exception(f"excel_get_workbook_structure failed: {e}")
        return f"Error: {str(e)}"


@function_tool
async def excel_get_sheet_summary(
    sheet: str,
    timeout_seconds: float = 30.0,
) -> str:
    """Get detailed summary of one sheet including data types and sample rows.

    Use after excel_get_workbook_structure() to dive deeper into a specific sheet.

    Args:
        sheet: Sheet name to analyze.
        timeout_seconds: Max wait time for Excel response. Default 30s.

    Returns:
        JSON: {
            "name": "KIRALAR",
            "dimensions": "A1:F40",
            "headers": ["", "date", "location", "amount", "currency", "ILS/TRY"],
            "column_types": {"A": "text", "B": "date", "C": "text", "D": "number", "E": "text", "F": "empty"},
            "empty_columns": ["F"],
            "formula_columns": [],
            "sample_rows": [["MIDTOWN", "01/01/2025", ...], ...],
            "row_count": 39
        }

    Example:
        # After seeing KIRALAR in workbook structure, get details
        result = excel_get_sheet_summary("KIRALAR")
        # See column types, empty columns, and sample data
    """
    reads = get_pending_reads()
    if reads is None:
        return "Error: Read context not initialized. Internal error."

    read_id = str(uuid.uuid4())
    loop = asyncio.get_event_loop()
    future: asyncio.Future = loop.create_future()
    reads[read_id] = future

    await _emit({
        "action": "get_sheet_summary",
        "sheet": sheet,
        "read_id": read_id,
    })

    try:
        result = await asyncio.wait_for(future, timeout=timeout_seconds)
        if result.get("success"):
            return json.dumps(result.get("data", {}))
        else:
            return f"Error: {result.get('error', 'Unknown error')}"
    except asyncio.TimeoutError:
        reads.pop(read_id, None)
        return f"Error: Sheet summary read timed out after {timeout_seconds}s for '{sheet}'."
    except asyncio.CancelledError:
        reads.pop(read_id, None)
        return "Error: Read cancelled."
    except Exception as e:
        reads.pop(read_id, None)
        logger.exception(f"excel_get_sheet_summary failed: {e}")
        return f"Error: {str(e)}"


@function_tool
async def excel_find_columns_by_header(
    pattern: str,
    timeout_seconds: float = 30.0,
) -> str:
    """Find columns across ALL sheets that match a header pattern.

    Useful for finding all columns with similar headers across multiple sheets
    (e.g., all FX rate columns, all date columns).

    Args:
        pattern: Search pattern (case-insensitive, supports * wildcard).
                 Examples: "*TRY*", "date", "*amount*"
        timeout_seconds: Max wait time for Excel response. Default 30s.

    Returns:
        JSON array: [
            {"sheet": "KIRALAR", "column": "F", "header": "ILS/TRY", "row_count": 39},
            {"sheet": "ILS Expenses", "column": "E", "header": "USD/TRY", "row_count": 25},
            ...
        ]

    Example:
        # Find all columns with TRY in the header (FX rates)
        result = excel_find_columns_by_header("*TRY*")
        # Returns matching columns from all sheets
    """
    reads = get_pending_reads()
    if reads is None:
        return "Error: Read context not initialized. Internal error."

    read_id = str(uuid.uuid4())
    loop = asyncio.get_event_loop()
    future: asyncio.Future = loop.create_future()
    reads[read_id] = future

    await _emit({
        "action": "find_columns_by_header",
        "pattern": pattern,
        "read_id": read_id,
    })

    try:
        result = await asyncio.wait_for(future, timeout=timeout_seconds)
        if result.get("success"):
            return json.dumps(result.get("data", []))
        else:
            return f"Error: {result.get('error', 'Unknown error')}"
    except asyncio.TimeoutError:
        reads.pop(read_id, None)
        return f"Error: Find columns timed out after {timeout_seconds}s for pattern '{pattern}'."
    except asyncio.CancelledError:
        reads.pop(read_id, None)
        return "Error: Read cancelled."
    except Exception as e:
        reads.pop(read_id, None)
        logger.exception(f"excel_find_columns_by_header failed: {e}")
        return f"Error: {str(e)}"


# ═══════════════════════════════════════════════════════════════════════════════
# Formatting
# ═══════════════════════════════════════════════════════════════════════════════


@function_tool
async def excel_format_range(
    sheet: str,
    range: str,
    bold: bool = False,
    italic: bool = False,
    fill: Optional[str] = None,
    font_color: Optional[str] = None,
    font_size: Optional[str] = None,
    number_format: Optional[str] = None,
    horizontal_alignment: Optional[str] = None,
    vertical_alignment: Optional[str] = None,
    wrap_text: bool = False,
    border_bottom: Optional[str] = None,
    border_top: Optional[str] = None,
    border_outline: Optional[str] = None,
) -> str:
    """Apply formatting to an existing range without changing values.

    Use after writing data to add visual styling.
    """
    # Sanitize optional params that LLMs sometimes pass as 'null' string
    fill = _sanitize_optional_str(fill)
    font_color = _sanitize_optional_str(font_color)
    font_size_int = _sanitize_optional_int(font_size)
    number_format = _sanitize_optional_str(number_format)
    horizontal_alignment = _sanitize_optional_str(horizontal_alignment)
    vertical_alignment = _sanitize_optional_str(vertical_alignment)
    border_bottom = _sanitize_optional_str(border_bottom)
    border_top = _sanitize_optional_str(border_top)
    border_outline = _sanitize_optional_str(border_outline)

    # ── Percentage format guardrail ──────────────────────────────────────
    # "0.0%" multiplies cell values by 100 for display.  A price of 274.08
    # would render as "27,408.0%".  Sample a few cells and block if any
    # numeric value has abs > 1.0 (legitimate percentage decimals stay
    # within ±1.0; anything beyond that is almost certainly not a decimal).
    if number_format and "%" in number_format:
        try:
            reads = get_pending_reads()
            if reads is not None:
                sample_id = str(uuid.uuid4())
                loop = asyncio.get_event_loop()
                future: asyncio.Future = loop.create_future()
                reads[sample_id] = future

                # Ask frontend for a small read of the target range
                await _emit({
                    "action": "read_range",
                    "sheet": sheet,
                    "range": range,
                    "read_id": sample_id,
                    "include_formulas": False,
                })

                result = await asyncio.wait_for(future, timeout=5.0)
                if result.get("success"):
                    values_2d = result.get("data", {}).get("values", [])
                    # Scan up to 5 rows for any numeric value with abs > 1.0
                    bad_val = None
                    for row in values_2d[:5]:
                        for v in row:
                            if isinstance(v, (int, float)) and abs(v) > 1.0:
                                bad_val = v
                                break
                        if bad_val is not None:
                            break
                    if bad_val is not None:
                        return (
                            f"Blocked: number_format '{number_format}' on {sheet}!{range} — "
                            f"sampled cells contain values like {bad_val}, which would display "
                            f"as '{bad_val * 100:.0f}%'. Percentage formats multiply by 100 "
                            f"for display and are designed for decimal values (e.g., 0.12 → "
                            f"'12.0%'). To fix: call excel_format_range separately for each "
                            f"column group — apply '{number_format}' only to "
                            f"return/percentage columns, and use '0.0000' or '#,##0.00' for "
                            f"price/value columns."
                        )
        except (asyncio.TimeoutError, asyncio.CancelledError):
            pass  # Read timed out — proceed without validation (non-blocking)
        except Exception:
            pass  # Any other read failure — proceed without validation
    # ── End percentage format guardrail ──────────────────────────────────

    fmt: Dict[str, Any] = {}
    if bold:
        fmt["bold"] = True
    if italic:
        fmt["italic"] = True
    if fill:
        fmt["fill"] = fill
    if font_color:
        fmt["font_color"] = font_color
    if font_size_int:
        fmt["font_size"] = font_size_int
    if number_format:
        fmt["number_format"] = number_format
    if horizontal_alignment:
        fmt["horizontal_alignment"] = horizontal_alignment
    if vertical_alignment:
        fmt["vertical_alignment"] = vertical_alignment
    if wrap_text:
        fmt["wrap_text"] = True
    borders: Dict[str, Any] = {}
    if border_bottom:
        borders["bottom"] = {"style": border_bottom}
    if border_top:
        borders["top"] = {"style": border_top}
    if border_outline:
        borders["outline"] = {"style": border_outline}
    if borders:
        fmt["borders"] = borders

    await _emit({
        "action": "format_range",
        "sheet": sheet,
        "operations": [{"range": range, "format": fmt}],
    })
    return f"Queued formatting for {sheet}!{range}."


# ═══════════════════════════════════════════════════════════════════════════════
# Charts
# ═══════════════════════════════════════════════════════════════════════════════


@function_tool
async def excel_create_chart(
    sheet: str,
    data_range: str,
    chart_type: str = "column",
    title: str = "",
    top: int = 200,
    left: int = 20,
    width: int = 500,
    height: int = 300,
    y_axis_min: Optional[float] = None,
    y_axis_max: Optional[float] = None,
) -> str:
    """Create a native Excel chart from data in the workbook.

    Args:
        sheet: Sheet containing the data AND where the chart will be placed.
        data_range: Range with headers + data (e.g. "A1:G8").
        chart_type: "bar", "barStacked", "column", "columnStacked", "line",
                    "lineMarkers", "pie", "area", "areaStacked", "scatter",
                    "scatterLines", "doughnut", "radar", "waterfall", "treemap",
                    "sunburst", "histogram", "boxWhisker", "surface",
                    "surfaceWireframe", "surfaceTopView", "surfaceTopViewWireframe".
        title: Chart title text.
        top: Vertical position in pixels from top of sheet.
        left: Horizontal position in pixels.
        width: Chart width in pixels.
        height: Chart height in pixels.
        y_axis_min: Minimum value for Y-axis. Use for narrow-range data (e.g., stock prices).
        y_axis_max: Maximum value for Y-axis. Use for narrow-range data (e.g., stock prices).
    """
    await _emit({
        "action": "create_chart",
        "sheet": sheet,
        "data_range": data_range,
        "chart_type": chart_type,
        "title": title,
        "top": top,
        "left": left,
        "width": width,
        "height": height,
        "y_axis_min": y_axis_min,
        "y_axis_max": y_axis_max,
    })
    return f"Chart '{title}' created on {sheet} from {data_range}."


# ═══════════════════════════════════════════════════════════════════════════════
# Layout & Structure
# ═══════════════════════════════════════════════════════════════════════════════


@function_tool
async def excel_autofit_columns(sheet: str, columns: List[str]) -> str:
    """Auto-fit column widths to content. Call after writing data.

    Args:
        sheet: Worksheet name.
        columns: Column letters or ranges (e.g. ["A", "B:G"]).
    """
    await _emit({"action": "autofit_columns", "sheet": sheet, "columns": columns})
    return f"Auto-fit columns {', '.join(columns)} on {sheet}."


@function_tool
async def excel_freeze_panes(sheet: str, cell: str) -> str:
    """Freeze rows above and columns left of the given cell.

    Args:
        sheet: Worksheet name.
        cell: Cell reference (e.g. "A2" freezes row 1, "B3" freezes rows 1-2 and column A).
    """
    await _emit({"action": "freeze_panes", "sheet": sheet, "cell": cell})
    return f"Froze panes at {sheet}!{cell}."


@function_tool
async def excel_set_column_widths(
    sheet: str,
    columns: List[str],
    width: int,
) -> str:
    """Set column widths for one or more columns to the same width.

    Args:
        sheet: Worksheet name.
        columns: Column letters or ranges (e.g. ["A", "B:H"]).
        width: Width in characters to apply to all specified columns.
    """
    widths_map = {col: width for col in columns}
    await _emit({"action": "set_column_widths", "sheet": sheet, "widths": widths_map})
    return f"Set column widths ({width} chars) for {', '.join(columns)} on {sheet}."


# ═══════════════════════════════════════════════════════════════════════════════
# Conditional Formatting
# ═══════════════════════════════════════════════════════════════════════════════


@function_tool
async def excel_add_conditional_format(
    sheet: str,
    range: str,
    format_type: str,
    color_scale: Optional[List[str]] = None,
    operator: Optional[str] = None,
    value: Optional[float] = None,
    format_fill: Optional[str] = None,
    format_font_color: Optional[str] = None,
) -> str:
    """Add conditional formatting to a range.

    Args:
        sheet: Worksheet name.
        range: Target range (e.g. "E2:E10").
        format_type: "colorScale", "dataBar", "iconSet", or "cellValue".
        color_scale: For colorScale — 2 or 3 hex colors (e.g. ["#FF0000", "#FFFF00", "#00B050"]).
        operator: For cellValue — "greaterThan", "lessThan", "between", etc.
        value: For cellValue — threshold value.
        format_fill: For cellValue — background color when condition is true.
        format_font_color: For cellValue — font color when condition is true.
    """
    rule: Dict[str, Any] = {"range": range, "type": format_type}
    if color_scale:
        rule["color_scale"] = color_scale
    if operator:
        rule["operator"] = operator
    if value is not None:
        rule["value"] = value
    if format_fill:
        rule["format_fill"] = format_fill
    if format_font_color:
        rule["format_font_color"] = format_font_color

    await _emit({
        "action": "add_conditional_format",
        "sheet": sheet,
        "rules": [rule],
    })
    return f"Queued conditional format ({format_type}) for {sheet}!{range}."


# ═══════════════════════════════════════════════════════════════════════════════
# Tables
# ═══════════════════════════════════════════════════════════════════════════════


@function_tool
async def excel_create_table(
    sheet: str,
    range: str,
    name: str,
    style: str = "TableStyleMedium2",
) -> str:
    """Create a structured Excel table with filtering and banding.

    Args:
        sheet: Worksheet name.
        range: Data range including headers (e.g. "A1:G8").
        name: Table name (must be unique, no spaces).
        style: Excel table style (e.g. "TableStyleMedium2", "TableStyleLight1").
    """
    await _emit({
        "action": "create_table",
        "sheet": sheet,
        "table": {"range": range, "name": name, "has_headers": True, "style": style},
    })
    return f"Table '{name}' created on {sheet} ({range})."


# ═══════════════════════════════════════════════════════════════════════════════
# Delete / Clear
# ═══════════════════════════════════════════════════════════════════════════════


@function_tool
async def excel_delete_sheet(name: str) -> str:
    """Delete a worksheet from the workbook. Irreversible."""
    reads = get_pending_reads()
    if reads is None:
        await _emit({"action": "delete_sheet", "name": name})
        return f"Sheet '{name}' deleted."

    op_id = str(uuid.uuid4())
    loop = asyncio.get_event_loop()
    future: asyncio.Future = loop.create_future()
    reads[op_id] = future

    await _emit({"action": "delete_sheet", "name": name, "read_id": op_id})

    try:
        result = await asyncio.wait_for(future, timeout=15.0)
        if result.get("success"):
            return f"Sheet '{name}' deleted."
        else:
            error = result.get("error", "Unknown error")
            return f"Error deleting sheet '{name}': {error}"
    except asyncio.TimeoutError:
        reads.pop(op_id, None)
        return f"Error: Sheet deletion timed out for '{name}'."
    except asyncio.CancelledError:
        reads.pop(op_id, None)
        return "Error: Sheet deletion cancelled."


@function_tool
async def excel_clear_range(sheet: str, range: str, clear_format: bool = False) -> str:
    """Clear cell contents (and optionally formatting) in a range.

    Args:
        sheet: Worksheet name.
        range: A1 notation range to clear.
        clear_format: If true, also clears formatting (not just values).
    """
    await _emit({
        "action": "clear_range",
        "sheet": sheet,
        "range": range,
        "clear_format": clear_format,
    })
    return f"Cleared {sheet}!{range}."


# ═══════════════════════════════════════════════════════════════════════════════
# Sort
# ═══════════════════════════════════════════════════════════════════════════════


@function_tool
async def excel_sort_range(
    sheet: str,
    range: str,
    key_column: int,
    ascending: bool = True,
) -> str:
    """Sort a data range by a column.

    Args:
        sheet: Worksheet name.
        range: Data range (e.g. "A2:G8" — exclude headers).
        key_column: 0-based column index within the range to sort by.
        ascending: Sort ascending (True) or descending (False).
    """
    await _emit({
        "action": "sort_range",
        "sheet": sheet,
        "sort": {"range": range, "key_column": key_column, "ascending": ascending},
    })
    return f"Sorted {sheet}!{range} by column {key_column} ({'asc' if ascending else 'desc'})."


# ═══════════════════════════════════════════════════════════════════════════════
# Row/Column Insert & Delete
# ═══════════════════════════════════════════════════════════════════════════════


@function_tool
async def excel_insert_rows(sheet: str, start_row: int, count: int = 1) -> str:
    """Insert blank rows above the given row number.

    Args:
        sheet: Worksheet name.
        start_row: Row number (1-based) above which to insert.
        count: Number of rows to insert.
    """
    await _emit({
        "action": "insert_rows",
        "sheet": sheet,
        "start_row": start_row,
        "count": min(count, 100),
    })
    return f"Inserted {count} row(s) above row {start_row} on {sheet}."


@function_tool
async def excel_delete_rows(sheet: str, start_row: int, count: int = 1) -> str:
    """Delete rows starting at the given row number.

    Args:
        sheet: Worksheet name.
        start_row: Row number (1-based) to start deleting from.
        count: Number of rows to delete.
    """
    await _emit({
        "action": "delete_rows",
        "sheet": sheet,
        "start_row": start_row,
        "count": min(count, 100),
    })
    return f"Deleted {count} row(s) starting at row {start_row} on {sheet}."


# ═══════════════════════════════════════════════════════════════════════════════
# Navigation / Activation
# ═══════════════════════════════════════════════════════════════════════════════


@function_tool
async def excel_activate_sheet(name: str) -> str:
    """Switch to (activate) a worksheet so the user can see it."""
    await _emit({"action": "activate_sheet", "name": name})
    return f"Activated sheet '{name}'."


# ═══════════════════════════════════════════════════════════════════════════════
# Data Validation
# ═══════════════════════════════════════════════════════════════════════════════


@function_tool
async def excel_add_data_validation(
    sheet: str,
    range: str,
    validation_type: str,
    formula1: Optional[str] = None,
    error_message: Optional[str] = None,
) -> str:
    """Add data validation (dropdown, numeric constraint) to cells.

    Args:
        sheet: Worksheet name.
        range: Target range.
        validation_type: "list", "decimal", "whole", or "custom".
        formula1: For list — comma-separated values (e.g. "Bull,Base,Bear").
                  For decimal/whole — min value. For custom — formula.
        error_message: Message shown when invalid input is entered.
    """
    rule: Dict[str, Any] = {
        "range": range,
        "type": validation_type,
    }
    if formula1:
        rule["formula1"] = formula1
    if error_message:
        rule["error_message"] = error_message

    await _emit({
        "action": "add_data_validation",
        "sheet": sheet,
        "validations": [rule],
    })
    return f"Data validation ({validation_type}) added to {sheet}!{range}."


# ═══════════════════════════════════════════════════════════════════════════════
# Named Ranges
# ═══════════════════════════════════════════════════════════════════════════════


@function_tool
async def excel_add_named_range(
    name: str,
    sheet: str,
    range: str,
    comment: Optional[str] = None,
) -> str:
    """Create a named range (workbook-scoped) for easier formula references.

    Args:
        name: Name for the range (e.g. "WACC", "RevenueGrowth"). No spaces.
        sheet: Worksheet containing the range.
        range: A1 notation (e.g. "B5").
        comment: Optional description.
    """
    await _emit({
        "action": "add_named_range",
        "named_ranges": [{"name": name, "sheet": sheet, "range": range, "comment": comment}],
    })
    return f"Named range '{name}' → {sheet}!{range}."


# ═══════════════════════════════════════════════════════════════════════════════
# Structure — Unified rows/columns operations
# ═══════════════════════════════════════════════════════════════════════════════


@function_tool
async def excel_structure(
    sheet: str,
    action: str,
    target: str = "rows",
    start: int = 1,
    count: int = 1,
    size: Optional[str] = None,
) -> str:
    """Unified tool for structural row/column operations.

    Handles insert, delete, hide, unhide, group, and ungroup for both
    rows and columns — plus setting row heights.

    Args:
        sheet: Worksheet name.
        action: One of "insert", "delete", "hide", "unhide",
                "group", "ungroup", "set_height".
        target: "rows" or "columns".
        start: 1-based start index (row number or column number).
        count: Number of rows/columns to affect (max 500).
        size: For "set_height" — height in points. Ignored otherwise.
    """
    size_int = _sanitize_optional_int(size)
    
    valid_actions = ("insert", "delete", "hide", "unhide", "group", "ungroup", "set_height")
    if action not in valid_actions:
        return f"Error: action must be one of {valid_actions}, got '{action}'."
    if target not in ("rows", "columns"):
        return f"Error: target must be 'rows' or 'columns', got '{target}'."
    count = min(count, 500)

    op: Dict[str, Any] = {
        "action": f"structure_{action}",
        "sheet": sheet,
        "target": target,
        "start": start,
        "count": count,
    }
    if action == "set_height" and size_int is not None:
        op["size"] = size_int

    await _emit(op)
    return f"{action.replace('_', ' ').title()} {count} {target} starting at {start} on {sheet}."


# ═══════════════════════════════════════════════════════════════════════════════
# Pivot Table
# ═══════════════════════════════════════════════════════════════════════════════


@function_tool
async def excel_pivot_table(
    source_sheet: str,
    source_range: str,
    dest_sheet: str,
    dest_cell: str,
    row_fields: List[str],
    value_fields_json: str,
    column_fields: Optional[List[str]] = None,
    filter_fields: Optional[List[str]] = None,
    name: str = "PivotTable1",
) -> str:
    """Create a PivotTable from a data range.

    Args:
        source_sheet: Sheet containing the source data.
        source_range: Data range including headers (e.g. "A1:G100").
        dest_sheet: Sheet where the pivot table will be placed (created if needed).
        dest_cell: Top-left cell for the pivot table (e.g. "A3").
        row_fields: Column header names to use as row labels (e.g. ["Sector", "Ticker"]).
        value_fields_json: JSON array of objects specifying value fields and aggregation.
            Example: '[{"field": "Revenue", "summarize_by": "sum"},
                       {"field": "PE_Ratio", "summarize_by": "average"}]'
            Valid summarize_by: "sum", "count", "average", "max", "min".
        column_fields: Optional header names for column labels.
        filter_fields: Optional header names for page/report filters.
        name: PivotTable name (unique, no spaces).
    """
    try:
        value_fields = json.loads(value_fields_json)
    except (json.JSONDecodeError, TypeError):
        return f"Error: value_fields_json is not valid JSON: {value_fields_json[:100]}"

    if not isinstance(value_fields, list) or not value_fields:
        return "Error: value_fields_json must be a non-empty array of objects."

    op: Dict[str, Any] = {
        "action": "create_pivot_table",
        "source_sheet": source_sheet,
        "source_range": source_range,
        "dest_sheet": dest_sheet,
        "dest_cell": dest_cell,
        "name": name,
        "row_fields": row_fields,
        "value_fields": value_fields,
    }
    if column_fields:
        op["column_fields"] = column_fields
    if filter_fields:
        op["filter_fields"] = filter_fields

    await _emit(op)
    return (
        f"PivotTable '{name}' created on {dest_sheet}!{dest_cell} "
        f"from {source_sheet}!{source_range}."
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Scenario / Sensitivity Table
# ═══════════════════════════════════════════════════════════════════════════════


@function_tool
async def excel_scenario_table(
    sheet: str,
    start_cell: str,
    title: str,
    row_input_cell: str,
    row_values_json: str,
    row_label: str,
    output_formula: str,
    col_input_cell: Optional[str] = None,
    col_values_json: Optional[str] = None,
    col_label: Optional[str] = None,
    number_format: str = "#,##0.00",
) -> str:
    """Build a one- or two-variable sensitivity / scenario table.

    Creates a formatted grid: row values along the left, column values along
    the top (if two-variable), output formula at the intersection, with
    institutional formatting applied.

    Args:
        sheet: Target worksheet.
        start_cell: Top-left cell for the table (e.g. "A1").
        title: Table title (e.g. "WACC vs. Terminal Growth Sensitivity").
        row_input_cell: The input cell that row values substitute into (e.g. "B5").
        row_values_json: JSON array of row-axis values (e.g. '[0.08, 0.09, 0.10, 0.11, 0.12]').
        row_label: Label for the row axis (e.g. "WACC").
        output_formula: The formula whose result varies (e.g. "=B20" pointing to DCF output).
        col_input_cell: For 2-variable — the second input cell.
        col_values_json: For 2-variable — JSON array of column-axis values.
        col_label: Label for the column axis (e.g. "Terminal Growth").
        number_format: Number format for output cells.
    """
    try:
        row_values = json.loads(row_values_json)
    except (json.JSONDecodeError, TypeError):
        return f"Error: row_values_json is not valid JSON: {row_values_json[:100]}"

    col_values = None
    if col_values_json:
        try:
            col_values = json.loads(col_values_json)
        except (json.JSONDecodeError, TypeError):
            return f"Error: col_values_json is not valid JSON: {col_values_json[:100]}"

    op: Dict[str, Any] = {
        "action": "create_scenario_table",
        "sheet": sheet,
        "start_cell": start_cell,
        "title": title,
        "row_input_cell": row_input_cell,
        "row_values": row_values,
        "row_label": row_label,
        "output_formula": output_formula,
        "number_format": number_format,
    }
    if col_input_cell and col_values:
        op["col_input_cell"] = col_input_cell
        op["col_values"] = col_values
        op["col_label"] = col_label or "Variable 2"
        table_type = "two-variable"
    else:
        table_type = "one-variable"

    await _emit(op)
    return (
        f"{table_type.title()} scenario table '{title}' created on "
        f"{sheet}!{start_cell} ({len(row_values)} row scenarios"
        f"{f', {len(col_values)} col scenarios' if col_values else ''})."
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Sheet Configuration
# ═══════════════════════════════════════════════════════════════════════════════


@function_tool
async def excel_sheet_config(
    sheet: str,
    tab_color: Optional[str] = None,
    protect: Optional[bool] = None,
    protect_password: Optional[str] = None,
    print_area: Optional[str] = None,
    orientation: Optional[str] = None,
    fit_to_page: Optional[bool] = None,
    show_gridlines: Optional[bool] = None,
    zoom: Optional[str] = None,
) -> str:
    """Configure sheet-level settings in one call.

    Args:
        sheet: Worksheet name.
        tab_color: Sheet tab color hex (e.g. "#00B050" for green, "#FF0000" for red).
        protect: True to protect sheet, False to unprotect.
        protect_password: Optional password for protection.
        print_area: Range to set as print area (e.g. "A1:K50"). None to clear.
        orientation: Page orientation: "portrait" or "landscape".
        fit_to_page: If True, scale to fit one page wide.
        show_gridlines: Show or hide cell gridlines.
        zoom: Zoom percentage (10-400).
    """
    # Sanitize optional params that LLMs sometimes pass as 'null' string
    tab_color = _sanitize_optional_str(tab_color)
    protect_password = _sanitize_optional_str(protect_password)
    print_area = _sanitize_optional_str(print_area)
    orientation = _sanitize_optional_str(orientation)
    zoom_int = _sanitize_optional_int(zoom)
    
    config: Dict[str, Any] = {}
    if tab_color is not None:
        config["tab_color"] = tab_color
    if protect is not None:
        config["protect"] = protect
        if protect_password:
            config["protect_password"] = protect_password
    if print_area is not None:
        config["print_area"] = print_area
    if orientation is not None:
        config["orientation"] = orientation
    if fit_to_page is not None:
        config["fit_to_page"] = fit_to_page
    if show_gridlines is not None:
        config["show_gridlines"] = show_gridlines
    if zoom_int is not None:
        config["zoom"] = max(10, min(400, zoom_int))

    if not config:
        return "No configuration changes specified."

    await _emit({"action": "sheet_config", "sheet": sheet, **config})
    applied = ", ".join(config.keys())
    return f"Sheet config updated on {sheet}: {applied}."


# ═══════════════════════════════════════════════════════════════════════════════
# Annotations — Comments & Hyperlinks
# ═══════════════════════════════════════════════════════════════════════════════


@function_tool
async def excel_annotations(
    sheet: str,
    cell: str,
    annotation_type: str,
    text: Optional[str] = None,
    url: Optional[str] = None,
    target_sheet: Optional[str] = None,
    target_cell: Optional[str] = None,
) -> str:
    """Add comments or hyperlinks to a cell.

    Args:
        sheet: Worksheet name.
        cell: Target cell (e.g. "A1").
        annotation_type: "comment" or "hyperlink".
        text: For comment — the comment text.
              For hyperlink — the display text (defaults to URL or target).
        url: For hyperlink — external URL (e.g. "https://...").
        target_sheet: For hyperlink — link to another sheet (internal link).
        target_cell: For hyperlink — cell in target_sheet to link to.
    """
    if annotation_type not in ("comment", "hyperlink"):
        return f"Error: annotation_type must be 'comment' or 'hyperlink', got '{annotation_type}'."

    op: Dict[str, Any] = {
        "action": f"add_{annotation_type}",
        "sheet": sheet,
        "cell": cell,
    }

    if annotation_type == "comment":
        if not text:
            return "Error: 'text' is required for comments."
        op["text"] = text
    elif annotation_type == "hyperlink":
        if url:
            op["url"] = url
            op["text"] = text or url
        elif target_sheet:
            op["target_sheet"] = target_sheet
            op["target_cell"] = target_cell or "A1"
            op["text"] = text or f"{target_sheet}!{target_cell or 'A1'}"
        else:
            return "Error: hyperlink requires either 'url' or 'target_sheet'."

    await _emit(op)
    return f"{annotation_type.title()} added to {sheet}!{cell}."


# ═══════════════════════════════════════════════════════════════════════════════
# Copy / Paste Range
# ═══════════════════════════════════════════════════════════════════════════════


@function_tool
async def excel_copy_range(
    source_sheet: str,
    source_range: str,
    dest_sheet: str,
    dest_start_cell: str,
    mode: str = "all",
    dest_end_cell: str = "",
) -> str:
    """Copy a range to another location with paste-special modes.

    When dest_end_cell is provided, the source pattern is tiled/repeated
    across the full destination range (like Excel's native Ctrl+C / select
    large area / Ctrl+V).  This is the recommended way to fill many rows
    from a single template row — one call instead of dozens of copies.

    Args:
        source_sheet: Source worksheet name.
        source_range: Source range (e.g. "A1:G20").
        dest_sheet: Destination worksheet name (can be same as source).
        dest_start_cell: Top-left cell of the destination (e.g. "A1").
        mode: Paste mode — "all" (values + formats + formulas),
              "values" (values only, no formulas), "formats" (formatting only),
              "transpose" (swap rows/columns).
        dest_end_cell: Optional bottom-right cell of the destination
              (e.g. "I252").  When provided, the source is tiled across the
              full dest_start_cell:dest_end_cell range, adjusting relative
              references per row/column.  Ideal for filling formulas down.
    """
    valid_modes = ("all", "values", "formats", "transpose")
    if mode not in valid_modes:
        return f"Error: mode must be one of {valid_modes}, got '{mode}'."

    dest_label = dest_start_cell
    if dest_end_cell:
        dest_label = f"{dest_start_cell}:{dest_end_cell}"

    op: dict = {
        "action": "copy_range",
        "source_sheet": source_sheet,
        "source_range": source_range,
        "dest_sheet": dest_sheet,
        "dest_start_cell": dest_start_cell,
        "mode": mode,
    }
    if dest_end_cell:
        op["dest_end_cell"] = dest_end_cell

    # Use confirmed (bidirectional) write when pending_reads is available
    reads = get_pending_reads()
    if reads is not None:
        op_id = str(uuid.uuid4())
        loop = asyncio.get_event_loop()
        future: asyncio.Future = loop.create_future()
        reads[op_id] = future
        op["read_id"] = op_id
        await _emit(op)

        try:
            result = await asyncio.wait_for(future, timeout=30.0)
            if result.get("success"):
                data = result.get("data") or {}
                rows = data.get("rows", "?")
                cols = data.get("cols", "?")
                return (
                    f"Copied {source_sheet}!{source_range} → "
                    f"{dest_sheet}!{dest_label} "
                    f"({rows} rows × {cols} cols, mode: {mode}, confirmed)."
                )
            else:
                error = result.get("error", "Unknown error")
                return (
                    f"Error copying {source_sheet}!{source_range} → "
                    f"{dest_sheet}!{dest_label}: {error}"
                )
        except asyncio.TimeoutError:
            reads.pop(op_id, None)
            return (
                f"WARNING: Copy {source_sheet}!{source_range} → "
                f"{dest_sheet}!{dest_label} timed out — may not have executed."
            )
        except asyncio.CancelledError:
            reads.pop(op_id, None)
            return "Error: Copy operation cancelled."

    # Fallback: fire-and-forget when pending_reads is not available
    await _emit(op)
    return (
        f"Copied {source_sheet}!{source_range} → {dest_sheet}!{dest_label} "
        f"(mode: {mode})."
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Auto-Filter
# ═══════════════════════════════════════════════════════════════════════════════


@function_tool
async def excel_auto_filter(
    sheet: str,
    action: str,
    range: Optional[str] = None,
    column_index: Optional[str] = None,
    criteria_json: Optional[str] = None,
) -> str:
    """Apply, configure, or clear auto-filters on a data range.

    Args:
        sheet: Worksheet name.
        action: "apply" (enable filter dropdowns), "set_criteria" (filter a column),
                "clear" (remove all filters), "clear_column" (clear one column's filter).
        range: Data range for "apply" (e.g. "A1:G100"). Ignored for clear.
        column_index: 0-based column index for "set_criteria" / "clear_column".
        criteria_json: For "set_criteria" — JSON object with filter spec.
            Examples:
              '{{"filterOn": "values", "values": ["AAPL", "MSFT"]}}'
              '{{"filterOn": "topItems", "count": 10}}'
              '{{"filterOn": "custom", "criterion1": ">1000000"}}'
    """
    # Sanitize optional params that LLMs sometimes pass as 'null' string
    range = _sanitize_optional_str(range)
    column_index_int = _sanitize_optional_int(column_index)
    criteria_json = _sanitize_optional_str(criteria_json)
    
    valid_actions = ("apply", "set_criteria", "clear", "clear_column")
    if action not in valid_actions:
        return f"Error: action must be one of {valid_actions}, got '{action}'."

    op: Dict[str, Any] = {"action": "auto_filter", "sheet": sheet, "filter_action": action}

    if action == "apply":
        if not range:
            return "Error: 'range' is required for 'apply' action."
        op["range"] = range
    elif action == "set_criteria":
        if column_index_int is None:
            return "Error: 'column_index' is required for 'set_criteria'."
        if not criteria_json:
            return "Error: 'criteria_json' is required for 'set_criteria'."
        try:
            criteria = json.loads(criteria_json)
        except (json.JSONDecodeError, TypeError):
            return f"Error: criteria_json is not valid JSON: {criteria_json[:100]}"
        op["column_index"] = column_index_int
        op["criteria"] = criteria
    elif action == "clear_column":
        if column_index_int is None:
            return "Error: 'column_index' is required for 'clear_column'."
        op["column_index"] = column_index_int

    await _emit(op)
    return f"Auto-filter {action} on {sheet}{f'!{range}' if range else ''}."


# ═══════════════════════════════════════════════════════════════════════════════
# VBA / Macro Code Generation
# ═══════════════════════════════════════════════════════════════════════════════


@function_tool
async def generate_vba_macro(
    title: str,
    code: str,
    purpose: str,
    instructions: str,
    sheets_involved: Optional[List[str]] = None,
) -> str:
    """Generate VBA macro code for the user to paste into the VBA Editor.

    Use this when the user asks for automation, macros, UDFs, event-driven
    logic, or anything that must persist in the workbook beyond this session.
    Office.js cannot inject VBA — the user must paste it manually.

    Args:
        title: Short name for the macro (e.g. "Highlight Duplicates").
        code: The complete VBA code (Sub/Function with End Sub/End Function).
        purpose: One-sentence description of what the macro does.
        instructions: Step-by-step instructions for the user to install the macro.
                      Always include: Alt+F11 → Insert Module → Paste → Close.
        sheets_involved: Optional list of sheet names the macro references.
    """
    await _emit({
        "action": "vba_code",
        "title": title,
        "code": code,
        "purpose": purpose,
        "instructions": instructions,
        "sheets_involved": sheets_involved or [],
    })
    return (
        f"VBA macro '{title}' generated and displayed to user. "
        f"Purpose: {purpose}. The user needs to paste it into the VBA Editor (Alt+F11)."
    )


# ═══════════════════════════════════════════════════════════════════════════════
# BH → Excel direct dump (bypasses agent context)
# ═══════════════════════════════════════════════════════════════════════════════


def _col_letter(n: int) -> str:
    """Convert 0-based column index to Excel letter (A, B, ..., Z, AA, ...)."""
    result = ""
    n += 1
    while n > 0:
        n, remainder = divmod(n - 1, 26)
        result = chr(65 + remainder) + result
    return result


@function_tool
async def bh_dump_to_excel(
    key: str,
    sheet: str,
    start_cell: str = "A1",
    columns: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_desc: bool = True,
    max_rows: int = 500,
    header_fill: str = "#1F4E79",
    header_font_color: str = "#FFFFFF",
    number_format: Optional[str] = None,
    autofit: bool = True,
) -> str:
    """Write a BinomialHash dataset directly to Excel WITHOUT loading data into context.

    This is the fastest way to dump BH data to a sheet. Data flows BH → Excel
    queue → Office.js, bypassing the LLM entirely. Use this instead of
    bh_to_excel + excel_write_values whenever you need to write BH data to Excel.

    Args:
        key: BH dataset key from the [BH] message.
        sheet: Target worksheet name.
        start_cell: Top-left cell for headers (e.g. "A1"). Data starts one row below.
        columns: Optional comma-separated column names to include (e.g. "ticker,volume,price").
                 Omit to include all columns.
        sort_by: Column name to sort by before writing.
        sort_desc: Sort descending (True) or ascending (False).
        max_rows: Maximum data rows to write (max 500). Does NOT include header row.
        header_fill: Header row background color hex.
        header_font_color: Header row font color hex.
        number_format: Optional Excel number format for data cells (e.g. "#,##0").
        autofit: Auto-fit column widths after writing (default True).
    """
    from core.agents.binomial_hash import get_binomial_hash
    import re
    import time as _time

    t0 = _time.perf_counter()
    bh = get_binomial_hash()
    slot = bh._get_slot(key)
    if slot is None:
        available = list(k for k in bh._slots.keys())
        return f"Error: BH key '{key}' not found. Available: {available}"

    col_list: Optional[List[str]] = None
    if columns:
        col_list = [c.strip() for c in columns.split(",") if c.strip()]

    batch = bh.to_excel_batch(key, col_list, sort_by, sort_desc, max_rows)
    if "error" in batch:
        return f"Error: {batch['error']}"

    headers = batch["headers"]
    values = batch["values"]
    if not headers or not values:
        return f"BH key '{key}' has no data to write."

    # Parse start cell to figure out column offset and row number
    m = re.match(r"([A-Z]+)(\d+)", start_cell.upper())
    if not m:
        return f"Error: invalid start_cell '{start_cell}'"
    start_col_letter = m.group(1)
    start_row = int(m.group(2))
    num_cols = len(headers)
    end_col_letter = _col_letter(
        sum((ord(c) - 64) * (26 ** i) for i, c in enumerate(reversed(start_col_letter))) - 1 + num_cols - 1
    )

    _pre_approved_token = _tool_pre_approved.set(False)
    try:
        friendly_label = batch.get("label", key).replace("_", " ").strip()
        await _request_tool_approval(
            f"write {len(values)} rows ({friendly_label}) to '{sheet}'"
        )

        # 0. Ensure sheet exists (bidirectional - waits for frontend confirmation)
        sheet_result = await _create_sheet_confirmed(sheet)
        if sheet_result.startswith("Error"):
            return sheet_result

        # 1. Write header row with formatting
        header_range = f"{start_col_letter}{start_row}:{end_col_letter}{start_row}"
        await _emit({
            "action": "write_cells",
            "sheet": sheet,
            "operations": [{
                "range": header_range,
                "values": [headers],
                "format": {
                    "bold": True,
                    "fill": header_fill,
                    "font_color": header_font_color,
                    "font_size": 11,
                    "horizontal_alignment": "center",
                    "borders": {"bottom": {"style": "medium"}},
                },
            }],
        })

        # 2. Write data in batches of 100 rows to avoid huge SSE payloads
        data_start_row = start_row + 1
        batch_size = 100
        for i in range(0, len(values), batch_size):
            chunk = values[i:i + batch_size]
            chunk_start = data_start_row + i
            chunk_end = chunk_start + len(chunk) - 1
            data_range = f"{start_col_letter}{chunk_start}:{end_col_letter}{chunk_end}"
            op: Dict[str, Any] = {"range": data_range, "values": chunk}
            if number_format:
                op["format"] = {"number_format": number_format}
            await _emit({
                "action": "write_cells",
                "sheet": sheet,
                "operations": [op],
            })

        # 3. Autofit columns
        if autofit:
            await _emit({
                "action": "autofit_columns",
                "sheet": sheet,
                "columns": [f"{start_col_letter}:{end_col_letter}"],
            })
    except OperationDeniedByUser as e:
        return str(e)
    finally:
        _tool_pre_approved.reset(_pre_approved_token)

    elapsed = (_time.perf_counter() - t0) * 1000
    total_cells = num_cols * len(values)
    logger.info(
        "[BH-perf] bh_dump_to_excel '%s' → %s!%s | %d cols x %d rows (%d cells) | %.1fms | 0 chars in agent context",
        key, sheet, start_cell, num_cols, len(values), total_cells, elapsed,
    )
    msg = (
        f"Queued {len(values)} rows x {num_cols} cols from BH '{key}' to {sheet}!{header_range} "
        f"(formatted headers) + {sheet}!{start_col_letter}{data_start_row}:{end_col_letter}{data_start_row + len(values) - 1} "
        f"(data). Total {total_cells} cells. {batch['total_available']} rows available in BH."
    )
    if batch.get("_truncation_note"):
        msg = f"⚠ TRUNCATED: {batch['_truncation_note']}\n{msg}"
    return msg


# ═══════════════════════════════════════════════════════════════════════════════
# Time-series Lookup Fill (FX rates, prices, etc.)
# ═══════════════════════════════════════════════════════════════════════════════


@function_tool
async def fill_column_from_bh_lookup(
    sheet: str,
    date_column: str,
    target_column: str,
    start_row: int,
    end_row: int,
    bh_key: str,
    date_field: str = "date",
    value_field: str = "price",
    bh_key_2: Optional[str] = None,
    value_field_2: Optional[str] = None,
    operation: str = "direct",
    lookup_sheet: str = "_Lookups",
) -> str:
    """Fill a column with XLOOKUP formulas referencing BH time-series data.

    Creates a lookup table from BH data and writes XLOOKUP formulas to target cells.
    Excel handles all date matching — the agent cannot mess up the lookup.

    Use this for FX rates, stock prices, economic indicators, or any time-series
    data that needs to be matched to dates in a spreadsheet.

    Args:
        sheet: Target worksheet name (e.g., "Rent").
        date_column: Column letter containing dates (e.g., "C").
        target_column: Column letter to fill with formulas (e.g., "E").
        start_row: First data row (1-based, e.g., 3 for row 3).
        end_row: Last data row (1-based, e.g., 38 for row 38).
        bh_key: BH dataset key containing lookup data.
        date_field: Column name in BH dataset for dates (default "date").
        value_field: Column name in BH dataset for values (default "price").
        bh_key_2: Second BH key for triangulated calculations (optional).
        value_field_2: Value field from second BH key (default same as value_field).
        operation: "direct" (use value_field), "divide" (key / key_2), "multiply" (key * key_2).
        lookup_sheet: Sheet name for lookup table (default "_Lookups").

    Returns:
        Success message with row count, or error message.

    Examples:
        # Direct lookup (USDTRY rates):
        fill_column_from_bh_lookup(
            sheet="USD Income", date_column="B", target_column="E",
            start_row=4, end_row=27, bh_key="forex_usdtry_abc123"
        )

        # Triangulated lookup (ILS/TRY = USDTRY / USDILS):
        fill_column_from_bh_lookup(
            sheet="Rent", date_column="C", target_column="E",
            start_row=3, end_row=38,
            bh_key="<bh_key_a>",
            bh_key_2="<bh_key_b>",
            operation="divide"
        )
    """
    from core.agents.binomial_hash import get_binomial_hash
    import time as _time

    t0 = _time.perf_counter()
    bh = get_binomial_hash()

    # Validate inputs
    if start_row < 1 or end_row < start_row:
        return f"Error: Invalid row range {start_row}:{end_row}"
    if len(date_column) > 2 or not date_column.isalpha():
        return f"Error: Invalid date_column '{date_column}'"
    if len(target_column) > 2 or not target_column.isalpha():
        return f"Error: Invalid target_column '{target_column}'"
    if operation not in ("direct", "divide", "multiply"):
        return f"Error: operation must be 'direct', 'divide', or 'multiply', got '{operation}'"

    # Validate BH keys exist
    slot1 = bh._get_slot(bh_key)
    if slot1 is None:
        available = list(bh._slots.keys())
        return f"Error: BH key '{bh_key}' not found. Available: {available}"

    if operation != "direct":
        if not bh_key_2:
            return f"Error: operation='{operation}' requires bh_key_2"
        slot2 = bh._get_slot(bh_key_2)
        if slot2 is None:
            available = list(bh._slots.keys())
            return f"Error: BH key '{bh_key_2}' not found. Available: {available}"

    # Use same value field for second key if not specified
    if value_field_2 is None:
        value_field_2 = value_field

    num_formulas = end_row - start_row + 1
    _pre_approved_token = _tool_pre_approved.set(False)
    try:
        await _request_tool_approval(
            f"write lookup data to {lookup_sheet} and {num_formulas} XLOOKUP formulas to {sheet}"
        )

        # 1. Create lookup sheet (bidirectional - waits for frontend confirmation)
        sheet_result = await _create_sheet_confirmed(lookup_sheet)
        if sheet_result.startswith("Error"):
            return sheet_result

        # 2. Dump first BH dataset to lookup sheet (columns A=date, B=value)
        batch1 = bh.to_excel_batch(bh_key, [date_field, value_field], date_field, False, 1000)
        if "error" in batch1:
            return f"Error retrieving BH key '{bh_key}': {batch1['error']}"
        if not batch1.get("values"):
            return f"Error: BH key '{bh_key}' has no data"

        headers1 = batch1["headers"]
        values1 = batch1["values"]
        num_rows1 = len(values1)

        # Write headers for first dataset
        await _emit({
            "action": "write_cells",
            "sheet": lookup_sheet,
            "operations": [{
                "range": "A1:B1",
                "values": [[date_field, value_field]],
                "format": {
                    "bold": True,
                    "fill": "#1F4E79",
                    "font_color": "#FFFFFF",
                },
            }],
        })

        # Write data for first dataset (in batches)
        batch_size = 100
        for i in range(0, num_rows1, batch_size):
            chunk = values1[i:i + batch_size]
            chunk_start = 2 + i
            chunk_end = chunk_start + len(chunk) - 1
            await _emit({
                "action": "write_cells",
                "sheet": lookup_sheet,
                "operations": [{"range": f"A{chunk_start}:B{chunk_end}", "values": chunk}],
            })

        # 3. If triangulated, dump second BH dataset to columns D, E (skip C as spacer)
        col_for_value2 = "D"
        if operation != "direct" and bh_key_2:
            batch2 = bh.to_excel_batch(bh_key_2, [date_field, value_field_2], date_field, False, 1000)
            if "error" in batch2:
                return f"Error retrieving BH key '{bh_key_2}': {batch2['error']}"
            if not batch2.get("values"):
                return f"Error: BH key '{bh_key_2}' has no data"

            values2 = batch2["values"]
            num_rows2 = len(values2)

            # Write headers for second dataset
            await _emit({
                "action": "write_cells",
                "sheet": lookup_sheet,
                "operations": [{
                    "range": "D1:E1",
                    "values": [[f"{date_field}_2", value_field_2]],
                    "format": {
                        "bold": True,
                        "fill": "#1F4E79",
                        "font_color": "#FFFFFF",
                    },
                }],
            })

            # Write data for second dataset
            for i in range(0, num_rows2, batch_size):
                chunk = values2[i:i + batch_size]
                chunk_start = 2 + i
                chunk_end = chunk_start + len(chunk) - 1
                await _emit({
                    "action": "write_cells",
                    "sheet": lookup_sheet,
                    "operations": [{"range": f"D{chunk_start}:E{chunk_end}", "values": chunk}],
                })

        # 4. Generate XLOOKUP formulas for each row
        formulas = []
        date_col = date_column.upper()
        lookup_sh = lookup_sheet

        for row in range(start_row, end_row + 1):
            date_cell = f"{date_col}{row}"
            if operation == "direct":
                formula = (
                    f'=IFERROR(XLOOKUP(INT({date_cell}),\'{lookup_sh}\'!$A:$A,\'{lookup_sh}\'!$B:$B,"",-1),"")'
                )
            elif operation == "divide":
                lookup1 = f'XLOOKUP(INT({date_cell}),\'{lookup_sh}\'!$A:$A,\'{lookup_sh}\'!$B:$B,"",-1)'
                lookup2 = f'XLOOKUP(INT({date_cell}),\'{lookup_sh}\'!$D:$D,\'{lookup_sh}\'!$E:$E,"",-1)'
                formula = f'=IFERROR({lookup1}/{lookup2},"")'
            elif operation == "multiply":
                lookup1 = f'XLOOKUP(INT({date_cell}),\'{lookup_sh}\'!$A:$A,\'{lookup_sh}\'!$B:$B,"",-1)'
                lookup2 = f'XLOOKUP(INT({date_cell}),\'{lookup_sh}\'!$D:$D,\'{lookup_sh}\'!$E:$E,"",-1)'
                formula = f'=IFERROR({lookup1}*{lookup2},"")'

            formulas.append([formula])

        # 5. Write all formulas at once
        target_col = target_column.upper()
        formula_range = f"{target_col}{start_row}:{target_col}{end_row}"

        await _emit({
            "action": "write_cells",
            "sheet": sheet,
            "operations": [{"range": formula_range, "formulas": formulas}],
        })

        # 6. Autofit the lookup sheet columns
        await _emit({
            "action": "autofit_columns",
            "sheet": lookup_sheet,
            "columns": ["A:E"],
        })
    except OperationDeniedByUser as e:
        return str(e)
    finally:
        _tool_pre_approved.reset(_pre_approved_token)

    elapsed = (_time.perf_counter() - t0) * 1000
    num_formulas = end_row - start_row + 1
    logger.info(
        "[BH-perf] fill_column_from_bh_lookup → %s!%s | %d formulas | %.1fms",
        sheet, formula_range, num_formulas, elapsed,
    )

    op_desc = operation if operation == "direct" else f"{operation} (triangulated)"
    return (
        f"Filled {num_formulas} rows in {sheet}!{formula_range} with XLOOKUP formulas ({op_desc}). "
        f"Lookup table created in '{lookup_sheet}' sheet with {num_rows1} rows."
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Export list for agent configuration
# ═══════════════════════════════════════════════════════════════════════════════

EXCEL_TOOLS = [
    # Sheet management
    excel_create_sheet,
    excel_rename_sheet,
    excel_delete_sheet,
    excel_activate_sheet,
    # Workbook discovery (tool-first architecture)
    excel_get_workbook_structure,
    excel_get_sheet_summary,
    excel_find_columns_by_header,
    # Reading (bidirectional - waits for frontend response)
    excel_read_range,
    # Writing
    excel_write_values,
    excel_write_formulas,
    excel_format_range,
    excel_clear_range,
    # Rows/columns
    excel_insert_rows,
    excel_delete_rows,
    excel_autofit_columns,
    excel_set_column_widths,
    excel_freeze_panes,
    # Charts
    excel_create_chart,
    # Tables & validation
    excel_create_table,
    excel_add_conditional_format,
    excel_add_data_validation,
    excel_add_named_range,
    # Sort
    excel_sort_range,
    # ── New power-user tools ──
    excel_structure,
    excel_pivot_table,
    excel_scenario_table,
    excel_sheet_config,
    excel_annotations,
    excel_copy_range,
    excel_auto_filter,
    # ── VBA / Macro ──
    generate_vba_macro,
    # ── BH direct dump ──
    bh_dump_to_excel,
    # ── Time-series lookup fill ──
    fill_column_from_bh_lookup,
]
