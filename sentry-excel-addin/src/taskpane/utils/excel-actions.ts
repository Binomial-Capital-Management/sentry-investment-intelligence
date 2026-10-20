/**
 * Office.js Excel Operations — Full Professional Toolkit
 *
 * All write operations target a SPECIFIC sheet.
 * Includes: write, read, create/rename/delete sheet, chart, merge, borders,
 * alignment, column widths, row heights, autofit, freeze panes, conditional
 * formatting, named ranges, data validation, tables, sort, protection.
 */

import {
  CellOperation,
  CellBorders,
  BorderEdge,
  ConditionalFormatRule,
  NamedRangeSpec,
  DataValidationSpec,
  TableSpec,
  SortSpec,
  SheetSnapshot,
  SerializedConditionalFormat,
  SerializedTable,
  SerializedChart,
  SerializedNamedRange,
  WorkbookCheckpoint,
} from "../../shared/types";

/* global Excel */

// ═══════════════════════════════════════════════════════════════════════════════
// Sheet Helpers
// ═══════════════════════════════════════════════════════════════════════════════

function getSheet(ctx: Excel.RequestContext, sheetName?: string): Excel.Worksheet {
  if (sheetName) return ctx.workbook.worksheets.getItem(sheetName);
  return ctx.workbook.worksheets.getActiveWorksheet();
}

function getSheetOrNull(ctx: Excel.RequestContext, name: string): Excel.Worksheet {
  return ctx.workbook.worksheets.getItemOrNullObject(name);
}

// ═══════════════════════════════════════════════════════════════════════════════
// Column/Row Address Helpers
// ═══════════════════════════════════════════════════════════════════════════════

function colLetterToNumber(col: string): number {
  let num = 0;
  for (let i = 0; i < col.length; i++) {
    num = num * 26 + (col.charCodeAt(i) - 64);
  }
  return num;
}

function numberToColLetter(num: number): string {
  let result = "";
  while (num > 0) {
    const rem = (num - 1) % 26;
    result = String.fromCharCode(65 + rem) + result;
    num = Math.floor((num - 1) / 26);
  }
  return result;
}

// ═══════════════════════════════════════════════════════════════════════════════
// Border Helpers
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Office.js borders use TWO properties:
 *   style  = line pattern (continuous, dash, dot, double, none)
 *   weight = line thickness (hairline, thin, medium, thick)
 *
 * Our agent-facing API uses a single "style" string that maps to both.
 * "thin"/"medium"/"thick" → continuous line with that weight.
 * "double"/"dotted"/"dashed"/"none" → that line pattern with thin weight.
 */
function applyBorderEdge(
  border: Excel.RangeBorder,
  edge: BorderEdge
): void {
  const s = edge.style || "thin";
  switch (s) {
    case "thin":
      border.style = "Continuous";
      border.weight = "Thin";
      break;
    case "medium":
      border.style = "Continuous";
      border.weight = "Medium";
      break;
    case "thick":
      border.style = "Continuous";
      border.weight = "Thick";
      break;
    case "double":
      border.style = "Double";
      border.weight = "Thin";
      break;
    case "dotted":
      border.style = "Dot";
      border.weight = "Thin";
      break;
    case "dashed":
      border.style = "Dash";
      border.weight = "Thin";
      break;
    case "none":
      border.style = "None";
      break;
    default:
      border.style = "Continuous";
      border.weight = "Thin";
  }
  if (edge.color) border.color = edge.color;
}

function applyBorders(range: Excel.Range, borders: CellBorders): void {
  if (borders.outline) {
    applyBorderEdge(range.format.borders.getItem(Excel.BorderIndex.edgeTop), borders.outline);
    applyBorderEdge(range.format.borders.getItem(Excel.BorderIndex.edgeBottom), borders.outline);
    applyBorderEdge(range.format.borders.getItem(Excel.BorderIndex.edgeLeft), borders.outline);
    applyBorderEdge(range.format.borders.getItem(Excel.BorderIndex.edgeRight), borders.outline);
  }
  if (borders.top) applyBorderEdge(range.format.borders.getItem(Excel.BorderIndex.edgeTop), borders.top);
  if (borders.bottom) applyBorderEdge(range.format.borders.getItem(Excel.BorderIndex.edgeBottom), borders.bottom);
  if (borders.left) applyBorderEdge(range.format.borders.getItem(Excel.BorderIndex.edgeLeft), borders.left);
  if (borders.right) applyBorderEdge(range.format.borders.getItem(Excel.BorderIndex.edgeRight), borders.right);
}

/**
 * Apply formatting to a single Range. Extracted so both single-range and
 * multi-range (comma-separated) code paths can share the same logic.
 */
function applyFormat(range: Excel.Range, f: NonNullable<CellOperation["format"]>, rangeAddr: string): void {
  // Font
  if (f.bold !== undefined) range.format.font.bold = f.bold;
  if (f.italic !== undefined) range.format.font.italic = f.italic;
  if (f.underline !== undefined) {
    range.format.font.underline = f.underline
      ? Excel.RangeUnderlineStyle.single
      : Excel.RangeUnderlineStyle.none;
  }
  if (f.strikethrough !== undefined) range.format.font.strikethrough = f.strikethrough;
  if (f.font_color) range.format.font.color = f.font_color;
  if (f.font_size) range.format.font.size = f.font_size;
  if (f.font_name) range.format.font.name = f.font_name;

  // Fill
  if (f.fill) range.format.fill.color = f.fill;

  // Number format — must be a 2D array matching the range dimensions
  if (f.number_format) {
    const nfDims = parseRangeDims(rangeAddr);
    if (nfDims) {
      const nfArr: string[][] = [];
      for (let nr = 0; nr < nfDims.rows; nr++) {
        const row: string[] = [];
        for (let nc = 0; nc < nfDims.cols; nc++) row.push(f.number_format);
        nfArr.push(row);
      }
      range.numberFormat = nfArr;
    } else {
      range.numberFormat = [[f.number_format]];
    }
  }

  // Alignment
  if (f.horizontal_alignment) {
    range.format.horizontalAlignment =
      (H_ALIGN_MAP[f.horizontal_alignment] || "General") as Excel.HorizontalAlignment;
  }
  if (f.vertical_alignment) {
    range.format.verticalAlignment =
      (V_ALIGN_MAP[f.vertical_alignment] || "Bottom") as Excel.VerticalAlignment;
  }
  if (f.wrap_text !== undefined) range.format.wrapText = f.wrap_text;
  if (f.indent !== undefined) range.format.indentLevel = f.indent;
  if (f.text_rotation !== undefined) range.format.textOrientation = f.text_rotation;

  // Borders
  if (f.borders) {
    applyBorders(range, f.borders);
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// Alignment Helpers
// ═══════════════════════════════════════════════════════════════════════════════

const H_ALIGN_MAP: Record<string, string> = {
  left: "Left",
  center: "Center",
  right: "Right",
  fill: "Fill",
  justify: "Justify",
  distributed: "Distributed",
};

const V_ALIGN_MAP: Record<string, string> = {
  top: "Top",
  center: "Center",
  bottom: "Bottom",
  justify: "Justify",
  distributed: "Distributed",
};

// ═══════════════════════════════════════════════════════════════════════════════
// Column Helpers (A → 1, AA → 27, etc.)
// ═══════════════════════════════════════════════════════════════════════════════

function colToNum(c: string): number {
  let n = 0;
  for (let i = 0; i < c.length; i++) n = n * 26 + (c.toUpperCase().charCodeAt(i) - 64);
  return n;
}

function colFromNum(n: number): string {
  let s = "";
  while (n > 0) {
    const rem = (n - 1) % 26;
    s = String.fromCharCode(65 + rem) + s;
    n = Math.floor((n - 1) / 26);
  }
  return s;
}

// ═══════════════════════════════════════════════════════════════════════════════
// Range Dimension Parser + Auto-Fixer
// ═══════════════════════════════════════════════════════════════════════════════

/** Parse "A1:G10" → { rows: 10, cols: 7 }. Single cell "B5" → { rows: 1, cols: 1 }. */
function parseRangeDims(addr: string): { rows: number; cols: number } | null {
  const m = addr.match(/^([A-Z]+)(\d+)(?::([A-Z]+)(\d+))?$/i);
  if (!m) return null;
  const c1 = colToNum(m[1]), r1 = parseInt(m[2], 10);
  if (!m[3]) return { rows: 1, cols: 1 };
  const c2 = colToNum(m[3]), r2 = parseInt(m[4], 10);
  return { rows: Math.abs(r2 - r1) + 1, cols: Math.abs(c2 - c1) + 1 };
}

/**
 * Fix a 2D array to match expected dimensions by padding/trimming.
 * - Too few rows → pad with empty rows
 * - Too many rows → trim
 * - Too few cols per row → pad with null
 * - Too many cols per row → trim
 */
function fixArrayDims(
  arr: (string | number | null)[][],
  rows: number,
  cols: number
): (string | number | null)[][] {
  const result: (string | number | null)[][] = [];
  for (let r = 0; r < rows; r++) {
    const srcRow = r < arr.length ? arr[r] : [];
    const row: (string | number | null)[] = [];
    for (let c = 0; c < cols; c++) {
      row.push(c < srcRow.length ? srcRow[c] : null);
    }
    result.push(row);
  }
  return result;
}

// ═══════════════════════════════════════════════════════════════════════════════
// Write Cells (full formatting: font, fill, borders, alignment, merge)
// ═══════════════════════════════════════════════════════════════════════════════

export async function writeCells(
  operations: CellOperation[],
  sheetName?: string
): Promise<number> {
  let applied = 0;
  await Excel.run(async (ctx) => {
    const sheet = getSheet(ctx, sheetName);
    const limit = Math.min(operations.length, 50);

    for (let i = 0; i < limit; i++) {
      const op = operations[i];

      // ── Comma-separated multi-ranges (e.g. "A2:A253,D2:D253,G2:G253") ──
      // Office.js getRange() only accepts a single range; split and handle each.
      if (op.range.includes(",")) {
        if (op.values || op.formulas || op.merge) {
          console.warn(`[writeCells] Cannot write values/formulas to comma-separated range: ${op.range}`);
          continue;
        }
        if (op.format) {
          const subRanges = op.range.split(",").map((r) => r.trim()).filter(Boolean);
          for (const sub of subRanges) {
            applyFormat(sheet.getRange(sub), op.format, sub);
          }
        }
        applied++;
        continue;
      }

      // ── Auto-fix array dimensions before writing ──
      const dims = parseRangeDims(op.range);
      if (dims) {
        if (op.values && Array.isArray(op.values)) {
          const vRows = op.values.length;
          const vCols = op.values[0]?.length || 0;
          if (vRows !== dims.rows || vCols !== dims.cols) {
            // If the range is "A1" (single cell) but values is a grid, expand the range
            if (dims.rows === 1 && dims.cols === 1 && (vRows > 1 || vCols > 1)) {
              // Compute the correct range from the values array dimensions
              const startMatch = op.range.match(/^([A-Z]+)(\d+)$/i);
              if (startMatch) {
                const startCol = startMatch[1].toUpperCase();
                const startRow = parseInt(startMatch[2], 10);
                const endCol = colFromNum(colToNum(startCol) + vCols - 1);
                const endRow = startRow + vRows - 1;
                op.range = `${startCol}${startRow}:${endCol}${endRow}`;
              }
            } else {
              // Pad or trim the values array to match the range
              op.values = fixArrayDims(op.values, dims.rows, dims.cols);
            }
          }
        }
        if (op.formulas && Array.isArray(op.formulas)) {
          const fRows = op.formulas.length;
          const fCols = op.formulas[0]?.length || 0;
          if (fRows !== dims.rows || fCols !== dims.cols) {
            if (dims.rows === 1 && dims.cols === 1 && (fRows > 1 || fCols > 1)) {
              const startMatch = op.range.match(/^([A-Z]+)(\d+)$/i);
              if (startMatch) {
                const startCol = startMatch[1].toUpperCase();
                const startRow = parseInt(startMatch[2], 10);
                const endCol = colFromNum(colToNum(startCol) + fCols - 1);
                const endRow = startRow + fRows - 1;
                op.range = `${startCol}${startRow}:${endCol}${endRow}`;
              }
            } else {
              op.formulas = fixArrayDims(
                op.formulas as (string | number | null)[][],
                dims.rows,
                dims.cols
              ) as (string | null)[][];
            }
          }
        }
      }

      const range = sheet.getRange(op.range);

      // Merge first (before writing values — merge keeps top-left value)
      if (op.merge) {
        range.merge(true);
      }

      if (op.values) range.values = op.values;
      if (op.formulas) range.formulas = op.formulas;

      if (op.format) {
        applyFormat(range, op.format, op.range);
      }
      applied++;
    }
    await ctx.sync();
  });
  return applied;
}

// ═══════════════════════════════════════════════════════════════════════════════
// Read Operations
// ═══════════════════════════════════════════════════════════════════════════════

export async function readRange(
  addr: string,
  sheetName?: string
): Promise<{ values: unknown[][]; formulas: unknown[][]; displayValues: unknown[][] }> {
  let result = { values: [] as unknown[][], formulas: [] as unknown[][], displayValues: [] as unknown[][] };

  await Excel.run(async (ctx) => {
    const sheet = getSheet(ctx, sheetName);
    const range = sheet.getRange(addr);
    range.load(["values", "formulas", "text"]);
    await ctx.sync();
    result = { values: range.values, formulas: range.formulas, displayValues: range.text };
  });

  return result;
}

export async function readWorkbookContext(): Promise<
  Record<string, { values: unknown[][]; formulas: unknown[][]; rows: number; cols: number }>
> {
  const sheets: Record<
    string,
    { values: unknown[][]; formulas: unknown[][]; rows: number; cols: number }
  > = {};

  await Excel.run(async (ctx) => {
    const worksheets = ctx.workbook.worksheets;
    worksheets.load("items/name");
    await ctx.sync();

    const limit = Math.min(worksheets.items.length, 100);
    for (let i = 0; i < limit; i++) {
      const ws = worksheets.items[i];
      const used = ws.getUsedRangeOrNullObject(true); // valuesOnly: ignore formatting-only cells
      used.load(["values", "formulas", "rowCount", "columnCount"]);
      await ctx.sync();

      if (used.isNullObject) continue;
      sheets[ws.name] = {
        values: used.values,
        formulas: used.formulas,
        rows: used.rowCount,
        cols: used.columnCount,
      };
    }
  });

  return sheets;
}

// ═══════════════════════════════════════════════════════════════════════════════
// Workbook Checkpoint — Comprehensive Snapshot & Restore
// ═══════════════════════════════════════════════════════════════════════════════

/** Default formatting values — cells matching all of these are skipped in sparse storage */
const FORMAT_DEFAULTS = {
  fontBold: false,
  fontItalic: false,
  fontStrikethrough: false,
  fontUnderline: "None",
  fontColor: "#000000",
  fontSize: 11,
  fontName: "Calibri",
  fillColor: "",
  fillPattern: "None",
  borderStyle: "None",
  horizontalAlignment: "General",
  verticalAlignment: "Bottom",
  wrapText: false,
  indentLevel: 0,
  textOrientation: 0,
  shrinkToFit: false,
};

function isDefaultFormat(cell: Record<string, unknown>): boolean {
  const fmt = cell.format as Record<string, unknown> | undefined;
  if (!fmt) return true;

  const font = fmt.font as Record<string, unknown> | undefined;
  if (font) {
    if (font.bold !== undefined && font.bold !== FORMAT_DEFAULTS.fontBold) return false;
    if (font.italic !== undefined && font.italic !== FORMAT_DEFAULTS.fontItalic) return false;
    if (font.strikethrough !== undefined && font.strikethrough !== FORMAT_DEFAULTS.fontStrikethrough) return false;
    if (font.underline !== undefined && font.underline !== FORMAT_DEFAULTS.fontUnderline) return false;
    if (font.color !== undefined && font.color !== "" && font.color !== FORMAT_DEFAULTS.fontColor) return false;
    if (font.size !== undefined && font.size !== FORMAT_DEFAULTS.fontSize) return false;
    if (font.name !== undefined && font.name !== FORMAT_DEFAULTS.fontName) return false;
  }

  const fill = fmt.fill as Record<string, unknown> | undefined;
  if (fill) {
    // Any non-empty fill color means non-default
    if (fill.color !== undefined && fill.color !== "" && fill.color !== FORMAT_DEFAULTS.fillColor) return false;
    if (fill.pattern !== undefined && fill.pattern !== FORMAT_DEFAULTS.fillPattern && fill.pattern !== "Solid") return false;
    if (fill.patternColor !== undefined && fill.patternColor !== "") return false;
  }

  const borders = fmt.borders as Record<string, unknown> | undefined;
  if (borders) {
    for (const edge of ["top", "bottom", "left", "right"]) {
      const b = (borders as Record<string, Record<string, unknown>>)[edge];
      if (b && b.style !== undefined && b.style !== FORMAT_DEFAULTS.borderStyle) return false;
    }
  }

  if (fmt.horizontalAlignment !== undefined && fmt.horizontalAlignment !== FORMAT_DEFAULTS.horizontalAlignment) return false;
  if (fmt.verticalAlignment !== undefined && fmt.verticalAlignment !== FORMAT_DEFAULTS.verticalAlignment) return false;
  if (fmt.wrapText !== undefined && fmt.wrapText !== FORMAT_DEFAULTS.wrapText) return false;
  if (fmt.indentLevel !== undefined && fmt.indentLevel !== 0 && fmt.indentLevel !== FORMAT_DEFAULTS.indentLevel) return false;
  if (fmt.textOrientation !== undefined && fmt.textOrientation !== 0 && fmt.textOrientation !== FORMAT_DEFAULTS.textOrientation) return false;
  if (fmt.shrinkToFit !== undefined && fmt.shrinkToFit !== FORMAT_DEFAULTS.shrinkToFit) return false;

  return true;
}

function stripSheetPrefix(address: string): string {
  const parts = address.split("!");
  return parts.length > 1 ? parts[1] : parts[0];
}

/**
 * Capture a comprehensive workbook snapshot for checkpoint/restore.
 * Reads: values, formulas, numberFormats, cell formatting, column widths,
 * row heights, freeze panes, protection, visibility, merged cells,
 * conditional formatting, tables, charts, and named ranges.
 */
export async function snapshotWorkbook(): Promise<{
  sheetNames: string[];
  sheets: Record<string, SheetSnapshot>;
  namedRanges: SerializedNamedRange[];
}> {
  const sheetNames: string[] = [];
  const sheets: Record<string, SheetSnapshot> = {};
  let namedRanges: SerializedNamedRange[] = [];

  await Excel.run(async (ctx) => {
    const worksheets = ctx.workbook.worksheets;
    worksheets.load("items/name");
    await ctx.sync();

    const limit = Math.min(worksheets.items.length, 100);

    for (let i = 0; i < limit; i++) {
      const ws = worksheets.items[i];
      sheetNames.push(ws.name);

      // ── Cell data ──
      const used = ws.getUsedRangeOrNullObject(true);
      used.load(["values", "formulas", "numberFormat", "address", "rowCount", "columnCount"]);

      // ── Sheet-level metadata ──
      ws.load(["protection/protected", "visibility"]);

      await ctx.sync();

      if (used.isNullObject) continue;

      const usedRangeAddress = stripSheetPrefix(used.address || "");

      // ── Cell formatting (chunked batch read to avoid payload limit) ──
      let cellFormats: Record<string, Record<string, unknown>> = {};
      const totalRows = used.rowCount;
      const totalCols = used.columnCount;
      // Target ~1500 cells per chunk to stay well within Excel's 5MB payload limit
      const CHUNK_ROWS = Math.max(10, Math.floor(1500 / Math.max(1, totalCols)));
      const cellPropSpec = {
        format: {
          font: { bold: true, italic: true, color: true, size: true, name: true,
                  strikethrough: true, underline: true },
          fill: { color: true, pattern: true, patternColor: true },
          borders: { color: true, style: true, weight: true },
          horizontalAlignment: true, verticalAlignment: true,
          wrapText: true, indentLevel: true, textOrientation: true,
          shrinkToFit: true, protection: true,
        },
      };

      for (let startRow = 0; startRow < totalRows; startRow += CHUNK_ROWS) {
        const rowsInChunk = Math.min(CHUNK_ROWS, totalRows - startRow);
        try {
          const chunk = used.getCell(startRow, 0).getResizedRange(rowsInChunk - 1, totalCols - 1);
          const cellProps = chunk.getCellProperties(cellPropSpec);
          await ctx.sync();

          const propsArray = cellProps.value;
          for (let r = 0; r < propsArray.length; r++) {
            for (let c = 0; c < propsArray[r].length; c++) {
              const cell = propsArray[r][c] as unknown as Record<string, unknown>;
              if (!isDefaultFormat(cell)) {
                // Extract only settable properties to avoid setCellProperties errors
                const rawFmt = cell.format as Record<string, unknown>;
                const cleanFmt: Record<string, unknown> = {};

                const rawFont = rawFmt.font as Record<string, unknown> | undefined;
                if (rawFont) {
                  const font: Record<string, unknown> = {};
                  if (rawFont.bold != null) font.bold = rawFont.bold;
                  if (rawFont.italic != null) font.italic = rawFont.italic;
                  if (rawFont.color != null) font.color = rawFont.color;
                  if (rawFont.size != null) font.size = rawFont.size;
                  if (rawFont.name != null) font.name = rawFont.name;
                  if (rawFont.strikethrough != null) font.strikethrough = rawFont.strikethrough;
                  if (rawFont.underline != null) font.underline = rawFont.underline;
                  if (Object.keys(font).length > 0) cleanFmt.font = font;
                }

                const rawFill = rawFmt.fill as Record<string, unknown> | undefined;
                if (rawFill) {
                  const fill: Record<string, unknown> = {};
                  if (rawFill.color != null && rawFill.color !== "") fill.color = rawFill.color;
                  if (rawFill.pattern != null && rawFill.pattern !== "None") fill.pattern = rawFill.pattern;
                  if (rawFill.patternColor != null && rawFill.patternColor !== "") fill.patternColor = rawFill.patternColor;
                  if (Object.keys(fill).length > 0) cleanFmt.fill = fill;
                }

                const rawBorders = rawFmt.borders as Record<string, Record<string, unknown>> | undefined;
                if (rawBorders) {
                  const cleanBorders: Record<string, unknown> = {};
                  for (const edge of ["top", "bottom", "left", "right"]) {
                    const b = rawBorders[edge];
                    if (b && b.style != null && b.style !== "None") {
                      const be: Record<string, unknown> = { style: b.style };
                      if (b.color != null) be.color = b.color;
                      if (b.weight != null) be.weight = b.weight;
                      cleanBorders[edge] = be;
                    }
                  }
                  if (Object.keys(cleanBorders).length > 0) cleanFmt.borders = cleanBorders;
                }

                if (rawFmt.horizontalAlignment != null) cleanFmt.horizontalAlignment = rawFmt.horizontalAlignment;
                if (rawFmt.verticalAlignment != null) cleanFmt.verticalAlignment = rawFmt.verticalAlignment;
                if (rawFmt.wrapText != null) cleanFmt.wrapText = rawFmt.wrapText;
                if (rawFmt.indentLevel != null) cleanFmt.indentLevel = rawFmt.indentLevel;
                if (rawFmt.textOrientation != null) cleanFmt.textOrientation = rawFmt.textOrientation;
                if (rawFmt.shrinkToFit != null) cleanFmt.shrinkToFit = rawFmt.shrinkToFit;

                cellFormats[`${startRow + r},${c}`] = cleanFmt;
              }
            }
          }
        } catch (fmtErr) {
          console.warn(`[checkpoint] getCellProperties chunk rows ${startRow}-${startRow + rowsInChunk - 1} FAILED for "${ws.name}":`, fmtErr);
        }
      }

      console.log(`[checkpoint] Sheet "${ws.name}": ${Object.keys(cellFormats).length} non-default cells captured`);

      // ── Column widths & row heights ──
      let columnWidths: number[] = [];
      let rowHeights: number[] = [];
      try {
        const colProps = used.getColumnProperties({ format: { columnWidth: true } });
        const rowProps = used.getRowProperties({ format: { rowHeight: true } });
        await ctx.sync();
        columnWidths = colProps.value.map((cp: unknown) => {
          const fmt = (cp as { format?: { columnWidth?: number } }).format;
          return fmt?.columnWidth ?? 0;
        });
        rowHeights = rowProps.value.map((rp: unknown) => {
          const fmt = (rp as { format?: { rowHeight?: number } }).format;
          return fmt?.rowHeight ?? 0;
        });
        console.log(`[checkpoint] Sheet "${ws.name}": ${columnWidths.length} colWidths, ${rowHeights.length} rowHeights`);
      } catch (dimErr) {
        console.error("[checkpoint] getColumnProperties/getRowProperties FAILED:", dimErr);
      }

      // ── Freeze panes ──
      let frozenRange: string | null = null;
      try {
        const frozen = ws.freezePanes.getLocationOrNullObject();
        frozen.load("address");
        await ctx.sync();
        if (!frozen.isNullObject) {
          frozenRange = stripSheetPrefix(frozen.address || "");
        }
      } catch (freezeErr) {
        console.error("[checkpoint] freezePanes FAILED:", freezeErr);
      }

      // ── Merged cells ──
      const mergedAreas: string[] = [];
      try {
        const merged = used.getMergedAreasOrNullObject();
        merged.load("areaCount");
        await ctx.sync();
        if (!merged.isNullObject && merged.areaCount > 0) {
          // address property only returns top-left cell — use rowCount/columnCount to reconstruct
          const areaRefs: Excel.Range[] = [];
          for (let i = 0; i < merged.areaCount; i++) {
            const area = merged.areas.getItemAt(i);
            area.load("address,rowCount,columnCount");
            areaRefs.push(area);
          }
          await ctx.sync();
          for (const area of areaRefs) {
            const topLeft = stripSheetPrefix(area.address);
            if (area.rowCount === 1 && area.columnCount === 1) {
              // Not actually merged (single cell), skip
              continue;
            }
            // Reconstruct full range from top-left + dimensions
            const match = topLeft.match(/^([A-Z]+)(\d+)$/);
            if (match) {
              const col = match[1];
              const row = parseInt(match[2]);
              // Convert column letter to number, add columnCount-1, convert back
              let colNum = 0;
              for (let c = 0; c < col.length; c++) {
                colNum = colNum * 26 + (col.charCodeAt(c) - 64);
              }
              const endColNum = colNum + area.columnCount - 1;
              const endRow = row + area.rowCount - 1;
              // Convert endColNum back to letter(s)
              let endCol = "";
              let n = endColNum;
              while (n > 0) {
                const rem = (n - 1) % 26;
                endCol = String.fromCharCode(65 + rem) + endCol;
                n = Math.floor((n - 1) / 26);
              }
              const fullAddr = `${col}${row}:${endCol}${endRow}`;
              mergedAreas.push(fullAddr);
            }
          }
        }
        console.log(`[checkpoint] Sheet "${ws.name}": ${mergedAreas.length} merged areas: ${mergedAreas.join(", ")}`);
      } catch (mergeErr) {
        console.error(`[checkpoint] getMergedAreas FAILED:`, mergeErr);
      }

      // ── Conditional formatting ──
      const conditionalFormats: SerializedConditionalFormat[] = [];
      try {
        const cfs = used.conditionalFormats;
        cfs.load("items/type,items/priority,items/stopIfTrue");
        await ctx.sync();

        for (const cf of cfs.items) {
          const entry: SerializedConditionalFormat = {
            type: cf.type,
            rangeAddress: "",
            priority: cf.priority,
            stopIfTrue: cf.stopIfTrue,
          };

          try {
            const cfRange = cf.getRange();
            cfRange.load("address");

            // Load type-specific properties
            if (cf.type === "CellValue") {
              cf.cellValue.load("rule");
              cf.cellValue.format.fill.load("color");
              cf.cellValue.format.font.load("color");
            } else if (cf.type === "ColorScale") {
              cf.colorScale.load("criteria");
            } else if (cf.type === "TopBottom") {
              cf.topBottom.load("rule");
              cf.topBottom.format.fill.load("color");
            } else if (cf.type === "Custom") {
              cf.custom.load("rule");
              cf.custom.format.fill.load("color");
              cf.custom.format.font.load("color");
            }

            await ctx.sync();
            entry.rangeAddress = stripSheetPrefix(cfRange.address);

            if (cf.type === "CellValue") {
              entry.cellValueRule = {
                operator: String(cf.cellValue.rule.operator || ""),
                formula1: cf.cellValue.rule.formula1 || "",
                formula2: cf.cellValue.rule.formula2,
                fillColor: cf.cellValue.format.fill.color || undefined,
                fontColor: cf.cellValue.format.font.color || undefined,
              };
            } else if (cf.type === "ColorScale") {
              entry.colorScaleCriteria = cf.colorScale.criteria;
            } else if (cf.type === "TopBottom") {
              entry.topBottomRule = {
                type: String(cf.topBottom.rule.type || ""),
                rank: cf.topBottom.rule.rank || 10,
                fillColor: cf.topBottom.format.fill.color || undefined,
              };
            } else if (cf.type === "Custom") {
              entry.customFormula = cf.custom.rule.formula || "";
              entry.customFillColor = cf.custom.format.fill.color || undefined;
              entry.customFontColor = cf.custom.format.font.color || undefined;
            }
          } catch {
            // Skip individual CF rules that fail to serialize
          }

          if (entry.rangeAddress) conditionalFormats.push(entry);
        }
      } catch {
        // Conditional formatting enumeration may fail
      }

      // ── Tables ──
      const tables: SerializedTable[] = [];
      try {
        const tbls = ws.tables;
        tbls.load("items/name,items/style,items/showHeaders,items/showBandedRows,items/showBandedColumns,items/showFilterButton");
        await ctx.sync();

        for (const tbl of tbls.items) {
          try {
            const tblRange = tbl.getRange();
            tblRange.load("address");
            await ctx.sync();
            tables.push({
              name: tbl.name,
              address: stripSheetPrefix(tblRange.address),
              hasHeaders: tbl.showHeaders,
              style: tbl.style,
              showBandedRows: tbl.showBandedRows,
              showBandedColumns: tbl.showBandedColumns,
              showFilterButton: tbl.showFilterButton,
            });
          } catch {
            // Skip individual tables that fail
          }
        }
      } catch {
        // Table enumeration may fail
      }

      // ── Charts ──
      const charts: SerializedChart[] = [];
      try {
        const chts = ws.charts;
        chts.load("items/name,items/chartType,items/left,items/top,items/width,items/height");
        await ctx.sync();

        for (const chart of chts.items) {
          let title = "";
          let sourceDataAddress: string | null = null;
          try {
            chart.title.load("text,visible");
            await ctx.sync();
            if (chart.title.visible) title = chart.title.text || "";
          } catch {
            // Title may not be accessible
          }
          try {
            const sd = (chart as unknown as { getDataRange?: () => Excel.Range }).getDataRange;
            if (sd) {
              const dataRange = sd.call(chart);
              dataRange.load("address");
              await ctx.sync();
              sourceDataAddress = stripSheetPrefix(dataRange.address);
            }
          } catch {
            // Source data may not be accessible in this API version
          }
          charts.push({
            name: chart.name,
            chartType: String(chart.chartType),
            title,
            left: chart.left,
            top: chart.top,
            width: chart.width,
            height: chart.height,
            sourceDataAddress,
          });
        }
      } catch {
        // Chart enumeration may fail
      }

      sheets[ws.name] = {
        values: used.values,
        formulas: used.formulas,
        numberFormats: used.numberFormat as string[][],
        rows: used.rowCount,
        cols: used.columnCount,
        usedRangeAddress,
        cellFormats,
        columnWidths,
        rowHeights,
        frozenRange,
        isProtected: ws.protection.protected,
        visibility: String(ws.visibility),
        mergedAreas,
        conditionalFormats,
        tables,
        charts,
      };
    }

    // ── Named ranges (workbook-level) ──
    try {
      ctx.workbook.names.load("items/name,items/formula,items/comment,items/visible");
      await ctx.sync();
      namedRanges = ctx.workbook.names.items.map((nr) => ({
        name: nr.name,
        formula: nr.formula,
        comment: nr.comment || "",
        visible: nr.visible,
      }));
    } catch {
      // Named ranges may fail
    }
  });

  return { sheetNames, sheets, namedRanges };
}

/**
 * Restore a workbook from a checkpoint snapshot.
 * Multi-phase: sheet management → content → formatting → objects → protection.
 */
export async function restoreWorkbook(checkpoint: WorkbookCheckpoint): Promise<void> {
  // ── Phase 1: Sheet management ──
  await Excel.run(async (ctx) => {
    const worksheets = ctx.workbook.worksheets;
    worksheets.load("items/name");
    await ctx.sync();

    const currentNames = worksheets.items.map((ws) => ws.name);
    const checkpointNames = new Set(checkpoint.sheetNames);

    // Delete sheets that weren't in checkpoint (keep ≥ 1)
    const toDelete = currentNames.filter((n) => !checkpointNames.has(n));
    if (currentNames.length - toDelete.length >= 1) {
      for (const name of toDelete) {
        const ws = worksheets.getItemOrNullObject(name);
        ws.load("isNullObject");
        await ctx.sync();
        if (!ws.isNullObject) {
          ws.delete();
          await ctx.sync();
        }
      }
    }

    // Create missing sheets
    for (const name of checkpoint.sheetNames) {
      const ws = worksheets.getItemOrNullObject(name);
      ws.load("isNullObject");
      await ctx.sync();
      if (ws.isNullObject) {
        worksheets.add(name);
        await ctx.sync();
      }
    }
  });

  // ── Phase 2: Content restore (per sheet) ──
  for (const [sheetName, data] of Object.entries(checkpoint.sheets)) {
    await Excel.run(async (ctx) => {
      const ws = ctx.workbook.worksheets.getItemOrNullObject(sheetName);
      ws.load("isNullObject,protection/protected");
      await ctx.sync();
      if (ws.isNullObject) return;

      // Unprotect if needed so we can write
      if (ws.protection.protected) {
        try { ws.protection.unprotect(); await ctx.sync(); } catch { /* may need password */ }
      }

      // Clear content on entire used range (removes agent's values)
      const currentUsed = ws.getUsedRangeOrNullObject(false);
      currentUsed.load("isNullObject");
      await ctx.sync();
      if (!currentUsed.isNullObject) {
        currentUsed.clear(Excel.ClearApplyTo.contents);
        await ctx.sync();
      }
      // Clear formatting only on the checkpoint's range (preserves formatting outside it, e.g. row 1)
      if (data.usedRangeAddress) {
        ws.getRange(data.usedRangeAddress).clear(Excel.ClearApplyTo.formats);
        await ctx.sync();
      }

      // Write formulas back (handles both formulas and plain values)
      if (data.usedRangeAddress && data.formulas && data.formulas.length > 0) {
        const range = ws.getRange(data.usedRangeAddress);
        range.formulas = data.formulas;
        await ctx.sync();
      }

      // Write number formats back
      if (data.usedRangeAddress && data.numberFormats && data.numberFormats.length > 0) {
        const range = ws.getRange(data.usedRangeAddress);
        range.numberFormat = data.numberFormats;
        await ctx.sync();
      }

      // (Merges applied in Phase 7 — the absolute last step, since all prior phases can unmerge)
    });
  }

  // ── Phase 3: Formatting restore (per sheet) ──
  for (const [sheetName, data] of Object.entries(checkpoint.sheets)) {
    await Excel.run(async (ctx) => {
      const ws = ctx.workbook.worksheets.getItemOrNullObject(sheetName);
      ws.load("isNullObject");
      await ctx.sync();
      if (ws.isNullObject || !data.usedRangeAddress) return;

      const range = ws.getRange(data.usedRangeAddress);

      // (Merges applied in Phase 7 — the absolute last step)

      // Cell formatting via setCellProperties (chunked to avoid payload limit)
      const formatKeys = Object.keys(data.cellFormats);
      if (formatKeys.length > 0) {
        const CHUNK_ROWS = Math.max(10, Math.floor(1500 / Math.max(1, data.cols)));
        for (let startRow = 0; startRow < data.rows; startRow += CHUNK_ROWS) {
          const rowsInChunk = Math.min(CHUNK_ROWS, data.rows - startRow);
          // Check if this chunk has any formatting to apply
          let hasFormats = false;
          for (let r = startRow; r < startRow + rowsInChunk && !hasFormats; r++) {
            for (let c = 0; c < data.cols && !hasFormats; c++) {
              if (data.cellFormats[`${r},${c}`]) hasFormats = true;
            }
          }
          if (!hasFormats) continue;

          try {
            const chunkProps: Record<string, unknown>[][] = [];
            for (let r = startRow; r < startRow + rowsInChunk; r++) {
              const row: Record<string, unknown>[] = [];
              for (let c = 0; c < data.cols; c++) {
                const fmt = data.cellFormats[`${r},${c}`];
                row.push(fmt ? { format: fmt } : {});
              }
              chunkProps.push(row);
            }
            const chunk = range.getCell(startRow, 0).getResizedRange(rowsInChunk - 1, data.cols - 1);
            chunk.setCellProperties(chunkProps as unknown as Excel.SettableCellProperties[][]);
            await ctx.sync();
          } catch (setCellErr) {
            console.warn(`[restore] setCellProperties chunk rows ${startRow}-${startRow + rowsInChunk - 1} FAILED for "${sheetName}":`, setCellErr);
          }
        }
      }

      // Column widths — apply to the columns of the used range (not absolute sheet columns)
      if (data.columnWidths.length > 0 && data.usedRangeAddress) {
        try {
          const usedForWidths = ws.getRange(data.usedRangeAddress);
          for (let c = 0; c < data.columnWidths.length; c++) {
            if (data.columnWidths[c] > 0) {
              const col = usedForWidths.getColumn(c);
              col.format.columnWidth = data.columnWidths[c];
            }
          }
          await ctx.sync();
          console.log(`[restore] Column widths restored for "${sheetName}": ${data.columnWidths.length} columns`);
        } catch (cwErr) {
          console.error(`[restore] Column widths FAILED for "${sheetName}":`, cwErr);
        }
      }

      // Row heights — apply to the rows of the used range (not absolute sheet rows)
      if (data.rowHeights.length > 0 && data.usedRangeAddress) {
        try {
          const usedForHeights = ws.getRange(data.usedRangeAddress);
          for (let r = 0; r < data.rowHeights.length; r++) {
            if (data.rowHeights[r] > 0) {
              const row = usedForHeights.getRow(r);
              row.format.rowHeight = data.rowHeights[r];
            }
          }
          await ctx.sync();
          console.log(`[restore] Row heights restored for "${sheetName}": ${data.rowHeights.length} rows`);
        } catch (rhErr) {
          console.error(`[restore] Row heights FAILED for "${sheetName}":`, rhErr);
        }
      }

      // Freeze panes
      try {
        if (data.frozenRange) {
          ws.freezePanes.freezeAt(ws.getRange(data.frozenRange));
        } else {
          ws.freezePanes.unfreeze();
        }
        await ctx.sync();
        console.log(`[restore] Freeze panes restored for "${sheetName}": ${data.frozenRange || "none"}`);
      } catch (freezeErr) {
        console.error(`[restore] Freeze panes FAILED for "${sheetName}":`, freezeErr);
      }
    });
  }

  // ── Phase 4: Workbook objects (per sheet) ──
  for (const [sheetName, data] of Object.entries(checkpoint.sheets)) {
    await Excel.run(async (ctx) => {
      const ws = ctx.workbook.worksheets.getItemOrNullObject(sheetName);
      ws.load("isNullObject");
      await ctx.sync();
      if (ws.isNullObject) return;

      // Conditional formatting: clear all on used range, re-add
      if (data.conditionalFormats.length > 0) {
        try {
          // Clear existing conditional formats via used range
          const clearUsed = ws.getUsedRangeOrNullObject(false);
          clearUsed.load("isNullObject");
          await ctx.sync();
          if (!clearUsed.isNullObject) {
            clearUsed.conditionalFormats.clearAll();
            await ctx.sync();
          }

          for (const cf of data.conditionalFormats) {
            try {
              const cfRange = ws.getRange(cf.rangeAddress);
              if (cf.type === "CellValue" && cf.cellValueRule) {
                const added = cfRange.conditionalFormats.add(
                  Excel.ConditionalFormatType.cellValue
                );
                added.cellValue.rule = {
                  operator: cf.cellValueRule.operator as Excel.ConditionalCellValueOperator,
                  formula1: cf.cellValueRule.formula1,
                  formula2: cf.cellValueRule.formula2,
                };
                if (cf.cellValueRule.fillColor) {
                  added.cellValue.format.fill.color = cf.cellValueRule.fillColor;
                }
                if (cf.cellValueRule.fontColor) {
                  added.cellValue.format.font.color = cf.cellValueRule.fontColor;
                }
              } else if (cf.type === "ColorScale" && cf.colorScaleCriteria) {
                const added = cfRange.conditionalFormats.add(
                  Excel.ConditionalFormatType.colorScale
                );
                added.colorScale.criteria = cf.colorScaleCriteria as Excel.ConditionalColorScaleCriteria;
              } else if (cf.type === "DataBar") {
                cfRange.conditionalFormats.add(Excel.ConditionalFormatType.dataBar);
              } else if (cf.type === "IconSet") {
                cfRange.conditionalFormats.add(Excel.ConditionalFormatType.iconSet);
              } else if (cf.type === "TopBottom" && cf.topBottomRule) {
                const added = cfRange.conditionalFormats.add(
                  Excel.ConditionalFormatType.topBottom
                );
                added.topBottom.rule = {
                  type: cf.topBottomRule.type as Excel.ConditionalTopBottomCriterionType,
                  rank: cf.topBottomRule.rank,
                };
                if (cf.topBottomRule.fillColor) {
                  added.topBottom.format.fill.color = cf.topBottomRule.fillColor;
                }
              } else if (cf.type === "Custom" && cf.customFormula) {
                const added = cfRange.conditionalFormats.add(
                  Excel.ConditionalFormatType.custom
                );
                added.custom.rule.formula = cf.customFormula;
                if (cf.customFillColor) {
                  added.custom.format.fill.color = cf.customFillColor;
                }
                if (cf.customFontColor) {
                  added.custom.format.font.color = cf.customFontColor;
                }
              }
            } catch {
              // Skip individual CF restoration failures
            }
          }
          await ctx.sync();
        } catch {
          // Skip conditional formatting restoration entirely if it fails
        }
      }

      // Tables: delete existing, recreate
      if (data.tables.length > 0) {
        try {
          const existingTables = ws.tables;
          existingTables.load("items/name");
          await ctx.sync();
          // Delete in reverse to avoid index shifting
          for (let t = existingTables.items.length - 1; t >= 0; t--) {
            existingTables.items[t].delete();
          }
          await ctx.sync();

          for (const tbl of data.tables) {
            try {
              const newTable = ws.tables.add(ws.getRange(tbl.address), tbl.hasHeaders);
              newTable.name = tbl.name;
              newTable.style = tbl.style;
              newTable.showBandedRows = tbl.showBandedRows;
              newTable.showBandedColumns = tbl.showBandedColumns;
              newTable.showFilterButton = tbl.showFilterButton;
            } catch {
              // Skip individual table creation failures
            }
          }
          await ctx.sync();
        } catch {
          // Skip table restoration entirely
        }
      }

      // Charts: delete existing, recreate (best effort)
      if (data.charts.length > 0) {
        try {
          const existingCharts = ws.charts;
          existingCharts.load("count");
          await ctx.sync();
          // Delete all existing charts
          while (existingCharts.count > 0) {
            existingCharts.getItemAt(0).delete();
            await ctx.sync();
            existingCharts.load("count");
            await ctx.sync();
          }

          for (const cht of data.charts) {
            try {
              if (!cht.sourceDataAddress) continue;
              const sourceRange = ws.getRange(cht.sourceDataAddress);
              const newChart = ws.charts.add(
                cht.chartType as Excel.ChartType,
                sourceRange,
                "Auto" as Excel.ChartSeriesBy
              );
              if (cht.title) {
                newChart.title.text = cht.title;
                newChart.title.visible = true;
              }
              newChart.left = cht.left;
              newChart.top = cht.top;
              newChart.width = cht.width;
              newChart.height = cht.height;
            } catch {
              // Skip individual chart creation failures
            }
          }
          await ctx.sync();
        } catch {
          // Skip chart restoration entirely
        }
      }
    });
  }

  // ── Phase 5: Named ranges ──
  if (checkpoint.namedRanges.length > 0) {
    await Excel.run(async (ctx) => {
      try {
        // Delete existing named ranges
        ctx.workbook.names.load("items/name");
        await ctx.sync();
        for (let i = ctx.workbook.names.items.length - 1; i >= 0; i--) {
          try { ctx.workbook.names.items[i].delete(); } catch { /* built-in names can't be deleted */ }
        }
        await ctx.sync();

        // Recreate from checkpoint
        for (const nr of checkpoint.namedRanges) {
          try {
            const item = ctx.workbook.names.add(nr.name, nr.formula, nr.comment);
            item.visible = nr.visible;
          } catch {
            // Skip individual named range failures
          }
        }
        await ctx.sync();
      } catch {
        // Skip named range restoration entirely
      }
    });
  }

  // ── Phase 6: Protection & visibility (LAST) ──
  await Excel.run(async (ctx) => {
    for (const [sheetName, data] of Object.entries(checkpoint.sheets)) {
      const ws = ctx.workbook.worksheets.getItemOrNullObject(sheetName);
      ws.load("isNullObject");
      await ctx.sync();
      if (ws.isNullObject) continue;

      // Visibility
      try {
        ws.visibility = data.visibility as Excel.SheetVisibility;
        await ctx.sync();
      } catch { /* skip visibility failures */ }

      // Protection
      if (data.isProtected) {
        try {
          ws.protection.protect({ selectionMode: Excel.ProtectionSelectionMode.normal });
          await ctx.sync();
        } catch { /* skip protection failures */ }
      }
    }

    // Delete sheets deferred from Phase 1 (if we had to keep ≥ 1)
    const worksheets = ctx.workbook.worksheets;
    worksheets.load("items/name");
    await ctx.sync();
    const checkpointNameSet = new Set(checkpoint.sheetNames);
    const extraSheets = worksheets.items.filter((ws) => !checkpointNameSet.has(ws.name));
    if (worksheets.items.length - extraSheets.length >= 1) {
      for (const ws of extraSheets) {
        try { ws.delete(); await ctx.sync(); } catch { /* skip */ }
      }
    }
  });

  // ── Phase 7: Merge cells (ABSOLUTE LAST — every prior phase can unmerge) ──
  for (const [sheetName, data] of Object.entries(checkpoint.sheets)) {
    if (!data.mergedAreas || data.mergedAreas.length === 0) continue;
    await Excel.run(async (ctx) => {
      const ws = ctx.workbook.worksheets.getItemOrNullObject(sheetName);
      ws.load("isNullObject");
      await ctx.sync();
      if (ws.isNullObject) return;

      for (const mergeAddr of data.mergedAreas) {
        try {
          ws.getRange(mergeAddr).merge(true);
        } catch { /* skip individual merge failures */ }
      }
      await ctx.sync();
      console.log(`[restore] Phase 7: Merged ${data.mergedAreas.length} areas in "${sheetName}": ${data.mergedAreas.join(", ")}`);
    });
  }
}

export async function readSheet(
  sheetName: string
): Promise<{ values: unknown[][]; formulas: unknown[][]; rows: number; cols: number } | null> {
  let result: { values: unknown[][]; formulas: unknown[][]; rows: number; cols: number } | null =
    null;

  await Excel.run(async (ctx) => {
    const ws = getSheetOrNull(ctx, sheetName);
    ws.load("isNullObject");
    await ctx.sync();

    if (ws.isNullObject) return;

    const used = ws.getUsedRangeOrNullObject(true); // valuesOnly: ignore formatting-only cells
    used.load(["values", "formulas", "rowCount", "columnCount"]);
    await ctx.sync();

    if (!used.isNullObject) {
      result = {
        values: used.values,
        formulas: used.formulas,
        rows: used.rowCount,
        cols: used.columnCount,
      };
    }
  });

  return result;
}

// ═══════════════════════════════════════════════════════════════════════════════
// Workbook Blueprint (compact structural overview for the agent)
// ═══════════════════════════════════════════════════════════════════════════════

export interface SheetBlueprint {
  name: string;
  rows: number;
  cols: number;
  headers: string[];
  has_formulas: boolean;
  sample_values: unknown[][];
}

export interface WorkbookBlueprint {
  sheets: SheetBlueprint[];
  total_sheets: number;
}

/**
 * Generate a compact blueprint of the workbook for the agent.
 * Much cheaper than readWorkbookContext — only reads headers + first 3 rows.
 */
export async function readWorkbookBlueprint(): Promise<WorkbookBlueprint> {
  const sheets: SheetBlueprint[] = [];

  await Excel.run(async (ctx) => {
    const worksheets = ctx.workbook.worksheets;
    worksheets.load("items/name");
    await ctx.sync();

    const limit = Math.min(worksheets.items.length, 20);
    for (let i = 0; i < limit; i++) {
      const ws = worksheets.items[i];
      const used = ws.getUsedRangeOrNullObject(true); // valuesOnly: ignore formatting-only cells
      used.load(["rowCount", "columnCount"]);
      await ctx.sync();

      if (used.isNullObject) {
        sheets.push({
          name: ws.name,
          rows: 0,
          cols: 0,
          headers: [],
          has_formulas: false,
          sample_values: [],
        });
        continue;
      }

      const rows = used.rowCount;
      const cols = used.columnCount;

      // Read first 3 rows (headers + 2 data rows) and formulas
      const sampleRows = Math.min(rows, 3);
      const sampleCols = Math.min(cols, 15);
      const sample = ws.getRangeByIndexes(0, 0, sampleRows, sampleCols);
      sample.load(["values", "formulas"]);
      await ctx.sync();

      const headers = (sample.values[0] || []).map((v: unknown) =>
        v != null && v !== "" ? String(v) : ""
      );

      const hasFormulas = sample.formulas.some((row: unknown[]) =>
        row.some((c: unknown) => typeof c === "string" && c.startsWith("="))
      );

      sheets.push({
        name: ws.name,
        rows,
        cols,
        headers,
        has_formulas: hasFormulas,
        sample_values: sample.values.slice(1), // skip header row
      });
    }
  });

  return { sheets, total_sheets: sheets.length };
}

// ═══════════════════════════════════════════════════════════════════════════════
// Sheet Management
// ═══════════════════════════════════════════════════════════════════════════════

export async function createSheet(name: string): Promise<void> {
  await Excel.run(async (ctx) => {
    const existing = getSheetOrNull(ctx, name);
    existing.load("isNullObject");
    await ctx.sync();
    if (!existing.isNullObject) return;
    const ws = ctx.workbook.worksheets.add(name);
    ws.activate();
    await ctx.sync();
  });
}

export async function renameSheet(oldName: string, newName: string): Promise<void> {
  await Excel.run(async (ctx) => {
    const ws = getSheet(ctx, oldName);
    ws.name = newName;
    await ctx.sync();
  });
}

export async function deleteSheet(name: string): Promise<void> {
  await Excel.run(async (ctx) => {
    const ws = getSheetOrNull(ctx, name);
    ws.load("isNullObject");
    await ctx.sync();
    if (ws.isNullObject) return;
    ws.delete();
    await ctx.sync();
  });
}

// ═══════════════════════════════════════════════════════════════════════════════
// Activate / Clear / Insert / Delete
// ═══════════════════════════════════════════════════════════════════════════════

export async function activateSheet(name: string): Promise<void> {
  await Excel.run(async (ctx) => {
    const ws = getSheetOrNull(ctx, name);
    ws.load("isNullObject");
    await ctx.sync();
    if (ws.isNullObject) return;
    ws.activate();
    await ctx.sync();
  });
}

export async function clearRange(
  sheetName: string,
  addr: string,
  clearFormat: boolean = false
): Promise<void> {
  await Excel.run(async (ctx) => {
    const sheet = getSheet(ctx, sheetName);
    const range = sheet.getRange(addr);
    if (clearFormat) {
      range.clear(Excel.ClearApplyTo.all);
    } else {
      range.clear(Excel.ClearApplyTo.contents);
    }
    await ctx.sync();
  });
}

// ═══════════════════════════════════════════════════════════════════════════════
// Copy Range (paste-special modes)
// ═══════════════════════════════════════════════════════════════════════════════

export async function copyRange(
  sourceSheet: string,
  sourceRange: string,
  destSheet: string,
  destStartCell: string,
  mode: string = "all",
  destEndCell: string = ""
): Promise<void> {
  await Excel.run(async (ctx) => {
    const srcSheet = getSheet(ctx, sourceSheet);
    const dstSheet = getSheet(ctx, destSheet);
    const srcRange = srcSheet.getRange(sourceRange);

    if (mode === "all" || mode === "formulas") {
      // Use copyFrom to properly adjust relative references (like Ctrl+C/V).
      // When destEndCell is provided, we construct the full destination range
      // so copyFrom tiles/repeats the source pattern across it — e.g. copying
      // one row of formulas into a 250-row destination fills all 250 rows with
      // correctly adjusted references, in a single call.
      const destAddr = destEndCell
        ? `${destStartCell}:${destEndCell}`
        : destStartCell;
      const dstRange = dstSheet.getRange(destAddr);
      const copyType =
        mode === "all"
          ? Excel.RangeCopyType.all
          : Excel.RangeCopyType.formulas;
      dstRange.copyFrom(srcRange, copyType);
      await ctx.sync();
      return;
    }

    if (mode === "formats") {
      const destAddr = destEndCell
        ? `${destStartCell}:${destEndCell}`
        : destStartCell;
      const dstRange = dstSheet.getRange(destAddr);
      dstRange.copyFrom(srcRange, Excel.RangeCopyType.formats);
      await ctx.sync();
      return;
    }

    // "values" and "transpose" require reading source data first.
    srcRange.load(["values", "rowCount", "columnCount"]);
    await ctx.sync();

    const rows = srcRange.rowCount;
    const cols = srcRange.columnCount;

    const startMatch = destStartCell.match(/^([A-Z]+)(\d+)$/i);
    if (!startMatch) {
      throw new Error(`Invalid destination cell: ${destStartCell}`);
    }
    const startCol = startMatch[1].toUpperCase();
    const startRow = parseInt(startMatch[2], 10);

    if (mode === "values") {
      const endCol = colFromNum(colToNum(startCol) + cols - 1);
      const endRow = startRow + rows - 1;
      const destRangeAddr = `${startCol}${startRow}:${endCol}${endRow}`;
      const dstRange = dstSheet.getRange(destRangeAddr);
      dstRange.values = srcRange.values;
    } else if (mode === "transpose") {
      const transposed: unknown[][] = [];
      for (let c = 0; c < cols; c++) {
        const row: unknown[] = [];
        for (let r = 0; r < rows; r++) {
          row.push(srcRange.values[r][c]);
        }
        transposed.push(row);
      }
      const transposeEndCol = colFromNum(colToNum(startCol) + rows - 1);
      const transposeEndRow = startRow + cols - 1;
      const transposedAddr = `${startCol}${startRow}:${transposeEndCol}${transposeEndRow}`;
      const transposedRange = dstSheet.getRange(transposedAddr);
      transposedRange.values = transposed;
    }

    await ctx.sync();
  });
}

export async function insertRows(
  sheetName: string,
  startRow: number,
  count: number = 1
): Promise<void> {
  await Excel.run(async (ctx) => {
    const sheet = getSheet(ctx, sheetName);
    const bounded = Math.min(count, 100);
    const range = sheet.getRangeByIndexes(startRow - 1, 0, bounded, 1);
    range.insert(Excel.InsertShiftDirection.down);
    await ctx.sync();
  });
}

export async function deleteRows(
  sheetName: string,
  startRow: number,
  count: number = 1
): Promise<void> {
  await Excel.run(async (ctx) => {
    const sheet = getSheet(ctx, sheetName);
    const bounded = Math.min(count, 100);
    const range = sheet.getRangeByIndexes(startRow - 1, 0, bounded, 1);
    range.delete(Excel.DeleteShiftDirection.up);
    await ctx.sync();
  });
}

// ═══════════════════════════════════════════════════════════════════════════════
// Hide / Unhide Rows and Columns
// ═══════════════════════════════════════════════════════════════════════════════

export async function hideRows(
  sheetName: string,
  startRow: number,
  count: number = 1
): Promise<void> {
  await Excel.run(async (ctx) => {
    const sheet = getSheet(ctx, sheetName);
    const bounded = Math.min(count, 500);
    const range = sheet.getRangeByIndexes(startRow - 1, 0, bounded, 1).getEntireRow();
    range.rowHidden = true;
    await ctx.sync();
  });
}

export async function unhideRows(
  sheetName: string,
  startRow: number,
  count: number = 1
): Promise<void> {
  await Excel.run(async (ctx) => {
    const sheet = getSheet(ctx, sheetName);
    const bounded = Math.min(count, 500);
    const range = sheet.getRangeByIndexes(startRow - 1, 0, bounded, 1).getEntireRow();
    range.rowHidden = false;
    await ctx.sync();
  });
}

export async function hideColumns(
  sheetName: string,
  startCol: number,
  count: number = 1
): Promise<void> {
  await Excel.run(async (ctx) => {
    const sheet = getSheet(ctx, sheetName);
    const bounded = Math.min(count, 500);
    const range = sheet.getRangeByIndexes(0, startCol - 1, 1, bounded).getEntireColumn();
    range.columnHidden = true;
    await ctx.sync();
  });
}

export async function unhideColumns(
  sheetName: string,
  startCol: number,
  count: number = 1
): Promise<void> {
  await Excel.run(async (ctx) => {
    const sheet = getSheet(ctx, sheetName);
    const bounded = Math.min(count, 500);
    const range = sheet.getRangeByIndexes(0, startCol - 1, 1, bounded).getEntireColumn();
    range.columnHidden = false;
    await ctx.sync();
  });
}

// ═══════════════════════════════════════════════════════════════════════════════
// Column Widths / Row Heights / Autofit
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Set column widths. Keys are column letters or ranges: {"A": 15, "B:D": 20}
 * Values are in character-width units (Excel default).
 */
export async function setColumnWidths(
  widths: Record<string, number>,
  sheetName?: string
): Promise<void> {
  await Excel.run(async (ctx) => {
    const sheet = getSheet(ctx, sheetName);
    for (const [col, width] of Object.entries(widths)) {
      // Expand "B:D" to a range the API understands
      const rangeAddr = col.includes(":") ? `${col.split(":")[0]}1:${col.split(":")[1]}1` : `${col}1`;
      const range = sheet.getRange(rangeAddr);
      range.format.columnWidth = width * 7.5; // character units → pixels (approx)
    }
    await ctx.sync();
  });
}

/**
 * Set row heights. Keys are row numbers or ranges: {"1": 30, "2:5": 18}
 * Values are in points.
 */
export async function setRowHeights(
  heights: Record<string, number>,
  sheetName?: string
): Promise<void> {
  await Excel.run(async (ctx) => {
    const sheet = getSheet(ctx, sheetName);
    for (const [row, height] of Object.entries(heights)) {
      const rangeAddr = row.includes(":") ? `A${row.split(":")[0]}:A${row.split(":")[1]}` : `A${row}`;
      const range = sheet.getRange(rangeAddr);
      range.format.rowHeight = height;
    }
    await ctx.sync();
  });
}

/**
 * Auto-fit columns to content. Accepts column letters or ranges: ["A", "B:G"]
 */
export async function autoFitColumns(
  columns: string[],
  sheetName?: string
): Promise<void> {
  await Excel.run(async (ctx) => {
    const sheet = getSheet(ctx, sheetName);
    for (const col of columns) {
      const rangeAddr = col.includes(":")
        ? `${col.split(":")[0]}:${col.split(":")[1]}`
        : `${col}:${col}`;
      const range = sheet.getRange(rangeAddr);
      range.format.autofitColumns();
    }
    await ctx.sync();
  });
}

// ═══════════════════════════════════════════════════════════════════════════════
// Freeze Panes
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Freeze panes at the given cell reference (Excel UI semantics).
 * E.g., "A2" freezes row 1, "B3" freezes rows 1-2 and column A.
 */
export async function freezePanes(
  cellRef: string,
  sheetName?: string
): Promise<void> {
  await Excel.run(async (ctx) => {
    const sheet = getSheet(ctx, sheetName);
    const match = cellRef.match(/^([A-Z]+)(\d+)$/i);
    if (!match) throw new Error(`Invalid cell reference for freeze: ${cellRef}`);
    const col = match[1].toUpperCase();
    const row = parseInt(match[2], 10);
    const colNum = colToNum(col);

    const rowsToFreeze = row - 1;
    const colsToFreeze = colNum - 1;

    if (rowsToFreeze > 0 && colsToFreeze === 0) {
      // Row-only freeze (e.g. "A2" → freeze first row across all columns)
      sheet.freezePanes.freezeRows(rowsToFreeze);
    } else if (rowsToFreeze === 0 && colsToFreeze > 0) {
      // Column-only freeze (e.g. "B1" → freeze column A across all rows)
      sheet.freezePanes.freezeColumns(colsToFreeze);
    } else if (rowsToFreeze > 0 && colsToFreeze > 0) {
      // Combined freeze (e.g. "B3" → freeze rows 1-2 and column A)
      const endCol = colFromNum(colsToFreeze);
      sheet.freezePanes.freezeAt(sheet.getRange(`A1:${endCol}${rowsToFreeze}`));
    }
    await ctx.sync();
  });
}

/**
 * Unfreeze all panes on a sheet.
 */
export async function unfreezePanes(sheetName?: string): Promise<void> {
  await Excel.run(async (ctx) => {
    const sheet = getSheet(ctx, sheetName);
    sheet.freezePanes.unfreeze();
    await ctx.sync();
  });
}

// ═══════════════════════════════════════════════════════════════════════════════
// Conditional Formatting
// ═══════════════════════════════════════════════════════════════════════════════

export async function addConditionalFormat(
  rules: ConditionalFormatRule[],
  sheetName?: string
): Promise<void> {
  await Excel.run(async (ctx) => {
    const sheet = getSheet(ctx, sheetName);

    for (const rule of rules) {
      const range = sheet.getRange(rule.range);

      if (rule.type === "colorScale" && rule.color_scale) {
        const cf = range.conditionalFormats.add(Excel.ConditionalFormatType.colorScale);
        const scale = cf.colorScale;
        const colors = rule.color_scale;
        if (colors.length >= 2) {
          scale.criteria = {
            minimum: { color: colors[0], type: Excel.ConditionalFormatColorCriterionType.lowestValue },
            maximum: { color: colors[colors.length - 1], type: Excel.ConditionalFormatColorCriterionType.highestValue },
            ...(colors.length >= 3
              ? { midpoint: { color: colors[1], type: Excel.ConditionalFormatColorCriterionType.percentile, formula: "50" } }
              : {}),
          };
        }
      } else if (rule.type === "dataBar") {
        range.conditionalFormats.add(Excel.ConditionalFormatType.dataBar);
        // Default data bar — Office.js auto-configures min/max
      } else if (rule.type === "iconSet") {
        range.conditionalFormats.add(Excel.ConditionalFormatType.iconSet);
      } else if (rule.type === "cellValue" && rule.operator && rule.value !== undefined) {
        const cf = range.conditionalFormats.add(Excel.ConditionalFormatType.cellValue);
        const cv = cf.cellValue;
        const opMap: Record<string, Excel.ConditionalCellValueOperator> = {
          greaterThan: Excel.ConditionalCellValueOperator.greaterThan,
          lessThan: Excel.ConditionalCellValueOperator.lessThan,
          equalTo: Excel.ConditionalCellValueOperator.equalTo,
          notEqualTo: Excel.ConditionalCellValueOperator.notEqualTo,
          greaterThanOrEqual: Excel.ConditionalCellValueOperator.greaterThanOrEqual,
          lessThanOrEqual: Excel.ConditionalCellValueOperator.lessThanOrEqual,
          between: Excel.ConditionalCellValueOperator.between,
        };
        const ruleSpec: Excel.ConditionalCellValueRule = {
          operator: opMap[rule.operator] || Excel.ConditionalCellValueOperator.greaterThan,
          formula1: String(rule.value),
        };
        if (rule.operator === "between" && rule.value2 !== undefined) {
          ruleSpec.formula2 = String(rule.value2);
        }
        cv.rule = ruleSpec;
        if (rule.format_fill) cv.format.fill.color = rule.format_fill;
        if (rule.format_font_color) cv.format.font.color = rule.format_font_color;
      } else if (rule.type === "top") {
        const cf = range.conditionalFormats.add(Excel.ConditionalFormatType.topBottom);
        cf.topBottom.rule = {
          type: Excel.ConditionalTopBottomCriterionType.topItems,
          rank: typeof rule.value === "number" ? rule.value : 10,
        };
        if (rule.format_fill) cf.topBottom.format.fill.color = rule.format_fill;
      }
    }
    await ctx.sync();
  });
}

// ═══════════════════════════════════════════════════════════════════════════════
// Named Ranges
// ═══════════════════════════════════════════════════════════════════════════════

export async function addNamedRanges(ranges: NamedRangeSpec[]): Promise<void> {
  await Excel.run(async (ctx) => {
    for (const nr of ranges) {
      const sheet = getSheet(ctx, nr.sheet);
      const range = sheet.getRange(nr.range);
      ctx.workbook.names.add(nr.name, range, nr.comment);
    }
    await ctx.sync();
  });
}

// ═══════════════════════════════════════════════════════════════════════════════
// Data Validation
// ═══════════════════════════════════════════════════════════════════════════════

export async function addDataValidation(
  validations: DataValidationSpec[],
  sheetName?: string
): Promise<void> {
  await Excel.run(async (ctx) => {
    const sheet = getSheet(ctx, sheetName);

    for (const v of validations) {
      const range = sheet.getRange(v.range);
      range.dataValidation.clear();

      if (v.type === "list") {
        range.dataValidation.rule = {
          list: { inCellDropDown: true, source: v.formula1 || "" },
        };
      } else if (v.type === "decimal" || v.type === "whole") {
        const opMap: Record<string, Excel.DataValidationOperator> = {
          between: Excel.DataValidationOperator.between,
          greaterThan: Excel.DataValidationOperator.greaterThan,
          lessThan: Excel.DataValidationOperator.lessThan,
          greaterThanOrEqual: Excel.DataValidationOperator.greaterThanOrEqualTo,
          lessThanOrEqual: Excel.DataValidationOperator.lessThanOrEqualTo,
          equalTo: Excel.DataValidationOperator.equalTo,
          notEqualTo: Excel.DataValidationOperator.notEqualTo,
        };
        const numRule: Excel.BasicDataValidation = {
          operator: opMap[v.operator || "between"] || Excel.DataValidationOperator.between,
          formula1: v.formula1 || "0",
          formula2: v.formula2 || undefined,
        };
        if (v.type === "decimal") {
          range.dataValidation.rule = { decimal: numRule };
        } else {
          range.dataValidation.rule = { wholeNumber: numRule };
        }
      } else if (v.type === "custom" && v.formula1) {
        range.dataValidation.rule = { custom: { formula: v.formula1 } };
      }

      if (v.show_error !== false && (v.error_title || v.error_message)) {
        range.dataValidation.errorAlert = {
          showAlert: true,
          title: v.error_title || "Invalid",
          message: v.error_message || "Please enter a valid value.",
          style: Excel.DataValidationAlertStyle.stop,
        };
      }
    }
    await ctx.sync();
  });
}

// ═══════════════════════════════════════════════════════════════════════════════
// Tables
// ═══════════════════════════════════════════════════════════════════════════════

export async function addTable(
  spec: TableSpec,
  sheetName?: string
): Promise<void> {
  await Excel.run(async (ctx) => {
    const sheet = getSheet(ctx, sheetName);
    const range = sheet.getRange(spec.range);
    const table = sheet.tables.add(range, spec.has_headers !== false);
    table.name = spec.name;
    if (spec.style) {
      table.style = spec.style;
    }
    await ctx.sync();
  });
}

// ═══════════════════════════════════════════════════════════════════════════════
// Sort
// ═══════════════════════════════════════════════════════════════════════════════

export async function sortRange(
  spec: SortSpec,
  sheetName?: string
): Promise<void> {
  await Excel.run(async (ctx) => {
    const sheet = getSheet(ctx, sheetName);
    const range = sheet.getRange(spec.range);
    range.sort.apply([
      {
        key: spec.key_column,
        ascending: spec.ascending !== false,
      },
    ]);
    await ctx.sync();
  });
}

// ═══════════════════════════════════════════════════════════════════════════════
// Sheet Protection
// ═══════════════════════════════════════════════════════════════════════════════

export async function protectSheet(
  sheetName?: string,
  password?: string
): Promise<void> {
  await Excel.run(async (ctx) => {
    const sheet = getSheet(ctx, sheetName);
    if (password) {
      sheet.protection.protect({ selectionMode: Excel.ProtectionSelectionMode.normal }, password);
    } else {
      sheet.protection.protect({ selectionMode: Excel.ProtectionSelectionMode.normal });
    }
    await ctx.sync();
  });
}

export async function unprotectSheet(
  sheetName?: string,
  password?: string
): Promise<void> {
  await Excel.run(async (ctx) => {
    const sheet = getSheet(ctx, sheetName);
    sheet.protection.unprotect(password);
    await ctx.sync();
  });
}

// ═══════════════════════════════════════════════════════════════════════════════
// Sheet Configuration (tab color, gridlines, zoom, print, orientation)
// ═══════════════════════════════════════════════════════════════════════════════

export interface SheetConfigOptions {
  tab_color?: string;
  protect?: boolean;
  protect_password?: string;
  print_area?: string;
  orientation?: string;
  fit_to_page?: boolean;
  show_gridlines?: boolean;
  zoom?: number;
}

export async function configureSheet(
  sheetName: string,
  config: SheetConfigOptions
): Promise<string[]> {
  const applied: string[] = [];
  await Excel.run(async (ctx) => {
    const sheet = getSheet(ctx, sheetName);

    if (config.tab_color !== undefined) {
      sheet.tabColor = config.tab_color;
      applied.push("tab_color");
    }

    if (config.show_gridlines !== undefined) {
      sheet.showGridlines = config.show_gridlines;
      applied.push("show_gridlines");
    }

    if (config.zoom !== undefined) {
      // Clamp to valid range
      const z = Math.max(10, Math.min(400, config.zoom));
      (sheet.pageLayout as any).zoom = { scale: z };
      applied.push("zoom");
    }

    if (config.orientation !== undefined) {
      sheet.pageLayout.orientation =
        config.orientation.toLowerCase() === "landscape"
          ? Excel.PageOrientation.landscape
          : Excel.PageOrientation.portrait;
      applied.push("orientation");
    }

    if (config.print_area !== undefined) {
      sheet.pageLayout.setPrintArea(config.print_area);
      applied.push("print_area");
    }

    if (config.fit_to_page !== undefined) {
      if (config.fit_to_page) {
        sheet.pageLayout.setPrintTitleRows("");
        (sheet.pageLayout as any).zoom = { fitToPage: true, fitToPagesWide: 1, fitToPagesTall: 0 };
      }
      applied.push("fit_to_page");
    }

    if (config.protect !== undefined) {
      if (config.protect) {
        if (config.protect_password) {
          sheet.protection.protect(
            { selectionMode: Excel.ProtectionSelectionMode.normal },
            config.protect_password
          );
        } else {
          sheet.protection.protect({ selectionMode: Excel.ProtectionSelectionMode.normal });
        }
      } else {
        sheet.protection.unprotect(config.protect_password);
      }
      applied.push("protect");
    }

    await ctx.sync();
  });
  return applied;
}

// ═══════════════════════════════════════════════════════════════════════════════
// Charts
// ═══════════════════════════════════════════════════════════════════════════════

export interface ChartCreateOptions {
  sheetName: string;
  dataRange: string;
  chartType?: string;
  title?: string;
  targetSheet?: string;
  left?: number;
  top?: number;
  width?: number;
  height?: number;
  yAxisMin?: number;
  yAxisMax?: number;
}

const CHART_TYPE_MAP: Record<string, string> = {
  bar: "BarClustered",
  barStacked: "BarStacked",
  column: "ColumnClustered",
  columnStacked: "ColumnStacked",
  line: "Line",
  lineMarkers: "LineMarkers",
  pie: "Pie",
  area: "Area",
  areaStacked: "AreaStacked",
  scatter: "XYScatter",
  scatterLines: "XYScatterLines",
  doughnut: "Doughnut",
  radar: "Radar",
  waterfall: "Waterfall",
  treemap: "Treemap",
  sunburst: "Sunburst",
  histogram: "Histogram",
  boxWhisker: "BoxWhisker",
  surface: "Surface",
  surfaceWireframe: "SurfaceWireframe",
  surfaceTopView: "SurfaceTopView",
  surfaceTopViewWireframe: "SurfaceTopViewWireframe",
  combo: "ColumnClustered",
};

export async function createChart(options: ChartCreateOptions): Promise<void> {
  await Excel.run(async (ctx) => {
    const sheet = getSheet(ctx, options.targetSheet || options.sheetName);
    const sourceSheet = getSheet(ctx, options.sheetName);
    
    const chartType = (CHART_TYPE_MAP[options.chartType || "column"] || "ColumnClustered") as Excel.ChartType;

    let chart: Excel.Chart;
    if (options.dataRange.includes(",")) {
      // Excel's charts.add() doesn't support RangeAreas, so we need to compute a bounding range
      const rangeAreas = sourceSheet.getRanges(options.dataRange);
      rangeAreas.load("areas/items/address");
      await ctx.sync();
      
      // Compute bounding range from all areas
      let minCol = Infinity, maxCol = -1, minRow = Infinity, maxRow = -1;
      for (const area of rangeAreas.areas.items) {
        const match = area.address.match(/!?\$?([A-Z]+)\$?(\d+):\$?([A-Z]+)\$?(\d+)/i) 
                   || area.address.match(/!?\$?([A-Z]+)\$?(\d+)/i);
        if (match) {
          const startCol = colLetterToNumber(match[1]);
          const startRow = parseInt(match[2], 10);
          const endCol = match[3] ? colLetterToNumber(match[3]) : startCol;
          const endRow = match[4] ? parseInt(match[4], 10) : startRow;
          minCol = Math.min(minCol, startCol, endCol);
          maxCol = Math.max(maxCol, startCol, endCol);
          minRow = Math.min(minRow, startRow, endRow);
          maxRow = Math.max(maxRow, startRow, endRow);
        }
      }
      const boundingRangeAddr = `${numberToColLetter(minCol)}${minRow}:${numberToColLetter(maxCol)}${maxRow}`;
      const boundingRange = sourceSheet.getRange(boundingRangeAddr);
      chart = sheet.charts.add(chartType, boundingRange, "Auto" as Excel.ChartSeriesBy);
    } else {
      const dataRange = sourceSheet.getRange(options.dataRange);
      chart = sheet.charts.add(chartType, dataRange, "Auto" as Excel.ChartSeriesBy);
    }

    if (options.title) {
      chart.title.text = options.title;
      chart.title.visible = true;
    }

    chart.left = options.left ?? 20;
    chart.top = options.top ?? 200;
    chart.width = options.width ?? 500;
    chart.height = options.height ?? 300;

    // Set Y-axis bounds if provided
    if (options.yAxisMin !== undefined || options.yAxisMax !== undefined) {
      const valueAxis = chart.axes.valueAxis;
      if (options.yAxisMin !== undefined) {
        valueAxis.minimum = options.yAxisMin;
      }
      if (options.yAxisMax !== undefined) {
        valueAxis.maximum = options.yAxisMax;
      }
    }

    await ctx.sync();
  });
}

// ═══════════════════════════════════════════════════════════════════════════════
// Auto Filter
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Apply, configure, or clear auto-filters on a data range.
 *
 * @param sheetName - Worksheet name
 * @param filterAction - "apply" | "set_criteria" | "clear" | "clear_column"
 * @param range - Data range for "apply" (e.g. "A1:G100")
 * @param columnIndex - 0-based column index for "set_criteria" / "clear_column"
 * @param criteria - Filter criteria object for "set_criteria"
 */
export async function applyAutoFilter(
  sheetName: string,
  filterAction: string,
  range?: string,
  columnIndex?: number,
  criteria?: Record<string, unknown>
): Promise<void> {
  await Excel.run(async (ctx) => {
    const sheet = getSheet(ctx, sheetName);

    switch (filterAction) {
      case "apply":
        if (range) {
          sheet.autoFilter.apply(sheet.getRange(range));
        }
        break;

      case "set_criteria":
        if (columnIndex !== undefined && criteria) {
          const filterRange = sheet.autoFilter.getRange();
          filterRange.load("address");
          await ctx.sync();

          let filterOn: Excel.FilterOn = Excel.FilterOn.values;
          let criterion1: string | undefined;
          let criterion2: string | undefined;
          let filterValues: string[] | undefined;

          if (criteria.values && Array.isArray(criteria.values)) {
            filterOn = Excel.FilterOn.values;
            filterValues = criteria.values as string[];
          } else if (criteria.criterion1) {
            filterOn = Excel.FilterOn.custom;
            criterion1 = criteria.criterion1 as string;
            if (criteria.criterion2) {
              criterion2 = criteria.criterion2 as string;
            }
          } else if (criteria.count !== undefined) {
            if (criteria.filterOn === "topItems") {
              filterOn = Excel.FilterOn.topItems;
            } else if (criteria.filterOn === "bottomItems") {
              filterOn = Excel.FilterOn.bottomItems;
            } else if (criteria.filterOn === "topPercent") {
              filterOn = Excel.FilterOn.topPercent;
            } else if (criteria.filterOn === "bottomPercent") {
              filterOn = Excel.FilterOn.bottomPercent;
            }
            criterion1 = String(criteria.count);
          } else if (criteria.filterOn) {
            filterOn = criteria.filterOn as Excel.FilterOn;
          }

          const filterCriteria: Excel.FilterCriteria = {
            filterOn,
            ...(filterValues && { values: filterValues }),
            ...(criterion1 && { criterion1 }),
            ...(criterion2 && { criterion2 }),
          };

          sheet.autoFilter.apply(filterRange, columnIndex, filterCriteria);
        }
        break;

      case "clear":
        sheet.autoFilter.clearCriteria();
        break;

      case "clear_column":
        if (columnIndex !== undefined) {
          sheet.autoFilter.clearColumnCriteria(columnIndex);
        }
        break;
    }

    await ctx.sync();
  });
}

// ═══════════════════════════════════════════════════════════════════════════════
// Workbook Discovery (Tool-First Architecture)
// ═══════════════════════════════════════════════════════════════════════════════

export interface SheetInfo {
  name: string;
  rows: number;
  cols: number;
  headers: string[];
  used_range: string;
}

export interface WorkbookStructure {
  sheets: SheetInfo[];
}

export interface SheetSummary {
  name: string;
  dimensions: string;
  headers: string[];
  column_types: Record<string, string>;
  empty_columns: string[];
  formula_columns: string[];
  sample_rows: unknown[][];
  row_count: number;
}

export interface ColumnMatch {
  sheet: string;
  column: string;
  header: string;
  row_count: number;
}

/**
 * Get overview of entire workbook - sheets, dimensions, and headers.
 * Call this FIRST to understand workbook structure before reading specific data.
 */
export async function getWorkbookStructure(): Promise<WorkbookStructure> {
  return Excel.run(async (ctx) => {
    const sheets = ctx.workbook.worksheets;
    sheets.load("items/name");
    await ctx.sync();

    const result: SheetInfo[] = [];
    for (const sheet of sheets.items) {
      const used = sheet.getUsedRangeOrNullObject(true); // valuesOnly: ignore formatting-only cells
      used.load(["address", "rowCount", "columnCount", "values"]);
      await ctx.sync();

      if (!used.isNullObject && used.values && used.values.length > 0) {
        const headers = used.values[0] || [];
        const addressParts = used.address ? used.address.split("!") : ["", ""];
        result.push({
          name: sheet.name,
          rows: used.rowCount,
          cols: used.columnCount,
          headers: headers.map((h: unknown) => String(h ?? "")),
          used_range: addressParts[1] || "",
        });
      } else {
        result.push({
          name: sheet.name,
          rows: 0,
          cols: 0,
          headers: [],
          used_range: "",
        });
      }
    }
    return { sheets: result };
  });
}

/**
 * Get detailed summary of one sheet including data types and sample rows.
 */
export async function getSheetSummary(sheetName: string): Promise<SheetSummary> {
  return Excel.run(async (ctx) => {
    const sheet = ctx.workbook.worksheets.getItem(sheetName);
    const used = sheet.getUsedRangeOrNullObject(true); // valuesOnly: ignore formatting-only cells
    used.load(["address", "rowCount", "columnCount", "values", "formulas"]);
    await ctx.sync();

    if (used.isNullObject || !used.values || used.values.length === 0) {
      return {
        name: sheetName,
        dimensions: "",
        headers: [],
        column_types: {},
        empty_columns: [],
        formula_columns: [],
        sample_rows: [],
        row_count: 0,
      };
    }

    const headers = used.values[0] || [];
    const sampleRows = used.values.slice(1, 4); // First 3 data rows

    // Detect column types and empty columns
    const columnTypes: Record<string, string> = {};
    const emptyColumns: string[] = [];
    const formulaColumns: string[] = [];

    for (let c = 0; c < headers.length; c++) {
      const col = numberToColLetter(c + 1);
      const colValues = used.values.slice(1).map((row: unknown[]) => row[c]);
      const colFormulas = used.formulas ? used.formulas.slice(1).map((row: unknown[]) => row[c]) : [];

      const nonEmpty = colValues.filter((v: unknown) => v != null && v !== "");

      if (nonEmpty.length === 0) {
        emptyColumns.push(col);
        columnTypes[col] = "empty";
      } else if (colFormulas.some((f: unknown) => typeof f === "string" && f.startsWith("="))) {
        formulaColumns.push(col);
        columnTypes[col] = "formula";
      } else if (nonEmpty.every((v: unknown) => typeof v === "number")) {
        columnTypes[col] = "number";
      } else if (nonEmpty.every((v: unknown) => {
        if (v instanceof Date) return true;
        if (typeof v === "string" && !isNaN(Date.parse(v))) return true;
        if (typeof v === "number" && v > 30000 && v < 100000) return true; // Excel date serial
        return false;
      })) {
        columnTypes[col] = "date";
      } else {
        columnTypes[col] = "text";
      }
    }

    const addressParts = used.address ? used.address.split("!") : ["", ""];

    return {
      name: sheetName,
      dimensions: addressParts[1] || "",
      headers: headers.map((h: unknown) => String(h ?? "")),
      column_types: columnTypes,
      empty_columns: emptyColumns,
      formula_columns: formulaColumns,
      sample_rows: sampleRows,
      row_count: used.rowCount - 1, // Exclude header row
    };
  });
}

/**
 * Find columns across ALL sheets that match a header pattern.
 * @param pattern - Search pattern (case-insensitive, supports * wildcard)
 */
export async function findColumnsByHeader(pattern: string): Promise<ColumnMatch[]> {
  return Excel.run(async (ctx) => {
    const sheets = ctx.workbook.worksheets;
    sheets.load("items/name");
    await ctx.sync();

    const matches: ColumnMatch[] = [];
    // Convert wildcard pattern to regex
    const regexPattern = pattern.replace(/\*/g, ".*");
    const regex = new RegExp(regexPattern, "i");

    for (const sheet of sheets.items) {
      const used = sheet.getUsedRangeOrNullObject(true); // valuesOnly: ignore formatting-only cells
      used.load(["values", "rowCount"]);
      await ctx.sync();

      if (!used.isNullObject && used.values && used.values.length > 0) {
        const headers = used.values[0] || [];
        headers.forEach((h: unknown, idx: number) => {
          const headerStr = String(h ?? "");
          if (headerStr && regex.test(headerStr)) {
            matches.push({
              sheet: sheet.name,
              column: numberToColLetter(idx + 1),
              header: headerStr,
              row_count: used.rowCount - 1, // Exclude header row
            });
          }
        });
      }
    }
    return matches;
  });
}
