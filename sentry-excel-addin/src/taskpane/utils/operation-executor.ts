import { AgentStep, CellOperation, TableSpec, ConditionalFormatRule, DataValidationSpec, NamedRangeSpec, SortSpec } from "../../shared/types";
import { postReadResponse } from "./sentry-api";
import { friendlyError } from "./friendly-error";
import {
  writeCells,
  readRange,
  createSheet,
  renameSheet,
  deleteSheet,
  activateSheet,
  clearRange,
  insertRows,
  deleteRows,
  hideRows,
  unhideRows,
  hideColumns,
  unhideColumns,
  createChart,
  autoFitColumns,
  setColumnWidths,
  setRowHeights,
  freezePanes,
  addConditionalFormat,
  addNamedRanges,
  addDataValidation,
  addTable,
  sortRange,
  protectSheet,
  copyRange,
  applyAutoFilter,
  getWorkbookStructure,
  getSheetSummary,
  findColumnsByHeader,
  configureSheet,
} from "./excel-actions";

// ─── Read-Operation Validation ───────────────────────────────────────────────

function validateReadOp(action: string, requestId: string | null | undefined, readId: string | undefined): boolean {
  if (!requestId) {
    console.error(`[executeOperation] ${action} requires requestId but none provided`);
    return false;
  }
  if (!readId) {
    console.error(`[executeOperation] ${action} missing read_id`);
    return false;
  }
  return true;
}

// ─── Tool-First Architecture Helpers ─────────────────────────────────────────

export const TOOL_FIRST_MAX_SHEETS = 10;
export const TOOL_FIRST_MAX_ROWS = 1000;

/**
 * Get the number of worksheets in the workbook.
 * Used to decide between tool-first and RAG paths.
 */
export async function getSheetCount(): Promise<number> {
  return Excel.run(async (ctx) => {
    const sheets = ctx.workbook.worksheets;
    sheets.load("items");
    await ctx.sync();
    return sheets.items.length;
  });
}

/**
 * Estimate total rows across the workbook by sampling first 5 sheets.
 * Used to decide between tool-first and RAG paths.
 */
export async function estimateTotalRows(): Promise<number> {
  return Excel.run(async (ctx) => {
    const sheets = ctx.workbook.worksheets;
    sheets.load("items");
    await ctx.sync();

    let total = 0;
    const sheetsToSample = sheets.items.slice(0, 5);
    for (const sheet of sheetsToSample) {
      const used = sheet.getUsedRangeOrNullObject(true);
      used.load("rowCount");
      await ctx.sync();
      if (!used.isNullObject) {
        total += used.rowCount;
      }
    }
    return total;
  });
}

// ─── Scenario Table Builder ─────────────────────────────────────────────────

/**
 * Parse a cell reference that may include a sheet name.
 * Examples: "B5" -> { sheet: null, range: "B5" }
 *           "Assumptions!B5" -> { sheet: "Assumptions", range: "B5" }
 *           "'Sheet Name'!B5" -> { sheet: "Sheet Name", range: "B5" }
 */
export function parseCellReference(ref: string): { sheet: string | null; range: string } {
  const match = ref.match(/^(?:'([^']+)'|([^'!]+))!(.+)$/);
  if (match) {
    const sheetName = match[1] || match[2];
    return { sheet: sheetName, range: match[3] };
  }
  return { sheet: null, range: ref };
}

/**
 * Get a range from the workbook, handling cross-sheet references.
 */
export function getRange(ctx: Excel.RequestContext, ref: string, defaultSheet: Excel.Worksheet): Excel.Range {
  const parsed = parseCellReference(ref);
  if (parsed.sheet) {
    return ctx.workbook.worksheets.getItem(parsed.sheet).getRange(parsed.range);
  }
  return defaultSheet.getRange(parsed.range);
}

export async function createScenarioTable(
  op: Record<string, unknown>,
  changedSheets: Set<string>
): Promise<void> {
  const sheetName = (op.sheet as string) || "Sensitivity";
  const startCell = (op.start_cell as string) || "A1";
  const title = (op.title as string) || "Sensitivity Analysis";
  const rowInputCell = op.row_input_cell as string;
  const rowValues = op.row_values as number[];
  const rowLabel = (op.row_label as string) || "Row Input";
  const outputFormula = op.output_formula as string;
  const numberFormat = (op.number_format as string) || "#,##0.00";
  const colInputCell = op.col_input_cell as string | undefined;
  const colValues = op.col_values as number[] | undefined;
  const colLabel = (op.col_label as string) || "Column Input";

  const outputRef = outputFormula?.startsWith("=") ? outputFormula.slice(1) : outputFormula;

  await Excel.run(async (ctx) => {
    const existingSheet = ctx.workbook.worksheets.getItemOrNullObject(sheetName);
    existingSheet.load("isNullObject");
    await ctx.sync();
    
    let sheet: Excel.Worksheet;
    if (existingSheet.isNullObject) {
      sheet = ctx.workbook.worksheets.add(sheetName);
    } else {
      sheet = existingSheet;
    }
    sheet.activate();

    const startMatch = startCell.match(/^([A-Z]+)(\d+)$/i);
    if (!startMatch) throw new Error(`Invalid start_cell: ${startCell}`);
    const startCol = startMatch[1].toUpperCase();
    const startRow = parseInt(startMatch[2], 10);

    const isTwoVariable = !!colInputCell && !!colValues && colValues.length > 0;

    const titleRange = sheet.getRange(`${startCol}${startRow}`);
    titleRange.values = [[title]];
    titleRange.format.font.bold = true;
    titleRange.format.font.size = 14;
    await ctx.sync();

    const rowInputRange = getRange(ctx, rowInputCell, sheet);
    const outputRange = getRange(ctx, outputRef, sheet);
    
    rowInputRange.load("values");
    let colInputRange: Excel.Range | null = null;
    if (isTwoVariable && colInputCell) {
      colInputRange = getRange(ctx, colInputCell, sheet);
      colInputRange.load("values");
    }
    await ctx.sync();
    
    const originalRowValue = rowInputRange.values[0][0];
    const originalColValue = colInputRange ? colInputRange.values[0][0] : null;

    if (isTwoVariable && colValues && colInputRange) {
      const dataStartRow = startRow + 2;
      const dataStartCol = startCol;

      const cornerCell = sheet.getRange(`${dataStartCol}${dataStartRow}`);
      cornerCell.values = [[rowLabel + " \\ " + colLabel]];
      cornerCell.format.font.bold = true;
      cornerCell.format.fill.color = "#1F4E79";
      cornerCell.format.font.color = "#FFFFFF";

      for (let c = 0; c < colValues.length; c++) {
        const colLetter = String.fromCharCode(dataStartCol.charCodeAt(0) + 1 + c);
        const cell = sheet.getRange(`${colLetter}${dataStartRow}`);
        cell.values = [[colValues[c]]];
        cell.numberFormat = [["0.0%"]];
        cell.format.font.bold = true;
        cell.format.fill.color = "#1F4E79";
        cell.format.font.color = "#FFFFFF";
        cell.format.horizontalAlignment = "Center";
      }

      for (let r = 0; r < rowValues.length; r++) {
        const cell = sheet.getRange(`${dataStartCol}${dataStartRow + 1 + r}`);
        cell.values = [[rowValues[r]]];
        cell.numberFormat = [["0.0%"]];
        cell.format.font.bold = true;
        cell.format.fill.color = "#D9E2F3";
      }
      await ctx.sync();

      const results: (number | string)[][] = [];
      for (let r = 0; r < rowValues.length; r++) {
        const rowResults: (number | string)[] = [];
        for (let c = 0; c < colValues.length; c++) {
          rowInputRange.values = [[rowValues[r]]];
          colInputRange.values = [[colValues[c]]];
          await ctx.sync();

          ctx.workbook.application.calculate(Excel.CalculationType.full);
          await ctx.sync();

          outputRange.load("values");
          await ctx.sync();
          rowResults.push(outputRange.values[0][0]);
        }
        results.push(rowResults);
      }

      for (let r = 0; r < rowValues.length; r++) {
        for (let c = 0; c < colValues.length; c++) {
          const colLetter = String.fromCharCode(dataStartCol.charCodeAt(0) + 1 + c);
          const cell = sheet.getRange(`${colLetter}${dataStartRow + 1 + r}`);
          cell.values = [[results[r][c]]];
          cell.numberFormat = [[numberFormat]];
        }
      }

      rowInputRange.values = [[originalRowValue]];
      colInputRange.values = [[originalColValue]];
      await ctx.sync();

    } else {
      const dataStartRow = startRow + 2;
      const outputCol = String.fromCharCode(startCol.charCodeAt(0) + 1);
      
      const headerRange = sheet.getRange(`${startCol}${dataStartRow}:${outputCol}${dataStartRow}`);
      headerRange.values = [[rowLabel, "Output"]];
      headerRange.format.font.bold = true;
      headerRange.format.fill.color = "#1F4E79";
      headerRange.format.font.color = "#FFFFFF";
      
      for (let r = 0; r < rowValues.length; r++) {
        const rowNum = dataStartRow + 1 + r;
        const inputCell = sheet.getRange(`${startCol}${rowNum}`);
        inputCell.values = [[rowValues[r]]];
        inputCell.numberFormat = [["0.0%"]];
      }
      await ctx.sync();

      const results: (number | string)[] = [];
      for (let r = 0; r < rowValues.length; r++) {
        rowInputRange.values = [[rowValues[r]]];
        await ctx.sync();

        ctx.workbook.application.calculate(Excel.CalculationType.full);
        await ctx.sync();

        outputRange.load("values");
        await ctx.sync();
        results.push(outputRange.values[0][0]);
      }

      for (let r = 0; r < rowValues.length; r++) {
        const rowNum = dataStartRow + 1 + r;
        const outputCell = sheet.getRange(`${outputCol}${rowNum}`);
        outputCell.values = [[results[r]]];
        outputCell.numberFormat = [[numberFormat]];
      }

      rowInputRange.values = [[originalRowValue]];
      await ctx.sync();
    }

    const usedRange = sheet.getUsedRange();
    usedRange.format.autofitColumns();
    await ctx.sync();

    changedSheets.add(sheetName);
  });
}

// ─── Execute Single Operation ─────────────────────────────────────────────────

export async function executeOperation(
  op: Record<string, unknown>,
  changedSheets: Set<string>,
  requestId?: string | null
): Promise<string | undefined> {
  const action = op.action as string;
  const sheet = op.sheet as string | undefined;

  switch (action) {
    case "create_sheet": {
      const createReadId = op.read_id as string | undefined;
      try {
        await createSheet(op.name as string);
        changedSheets.add(op.name as string);
        if (createReadId && requestId) {
          await postReadResponse(requestId, createReadId, { success: true });
        }
      } catch (err) {
        if (createReadId && requestId) {
          await postReadResponse(requestId, createReadId, {
            success: false,
            error: err instanceof Error ? err.message : "Failed to create sheet",
          });
        } else {
          throw err;
        }
      }
      break;
    }
    case "rename_sheet": {
      const renameReadId = op.read_id as string | undefined;
      try {
        await renameSheet(op.old_name as string, op.new_name as string);
        if (renameReadId && requestId) {
          await postReadResponse(requestId, renameReadId, { success: true });
        }
      } catch (err) {
        if (renameReadId && requestId) {
          await postReadResponse(requestId, renameReadId, {
            success: false,
            error: err instanceof Error ? err.message : "Failed to rename sheet",
          });
        } else {
          throw err;
        }
      }
      break;
    }
    case "delete_sheet": {
      const deleteReadId = op.read_id as string | undefined;
      try {
        await deleteSheet(op.name as string);
        if (deleteReadId && requestId) {
          await postReadResponse(requestId, deleteReadId, { success: true });
        }
      } catch (err) {
        if (deleteReadId && requestId) {
          await postReadResponse(requestId, deleteReadId, {
            success: false,
            error: err instanceof Error ? err.message : "Failed to delete sheet",
          });
        } else {
          throw err;
        }
      }
      break;
    }
    case "activate_sheet":
      await activateSheet(op.name as string);
      break;

    case "read_range": {
      const readSheet = sheet || (op.sheet as string);
      const rangeAddr = op.range as string;
      const readId = op.read_id as string;
      const includeFormulas = op.include_formulas !== false;

      if (!validateReadOp("read_range", requestId, readId)) break;

      try {
        const data = await readRange(rangeAddr, readSheet);
        await postReadResponse(requestId!, readId, {
          success: true,
          data: {
            values: data.values,
            formulas: includeFormulas ? data.formulas : [],
            display_values: data.displayValues,
          },
        });

        const rowCount = data.values?.length || 0;
        const colCount = data.values?.[0]?.length || 0;
        return `${readSheet}!${rangeAddr} (${rowCount}×${colCount})`;
      } catch (err) {
        console.error("[executeOperation] read_range failed:", err);
        await postReadResponse(requestId!, readId, {
          success: false,
          error: err instanceof Error ? err.message : "Unknown error reading range",
        });
        return `${readSheet}!${rangeAddr} (failed)`;
      }
    }

    case "get_workbook_structure": {
      const readId = op.read_id as string;
      if (!validateReadOp("get_workbook_structure", requestId, readId)) break;
      try {
        const structure = await getWorkbookStructure();
        await postReadResponse(requestId!, readId, { success: true, data: structure });
        return `Workbook structure: ${structure.sheets.length} sheets`;
      } catch (err) {
        console.error("[executeOperation] get_workbook_structure failed:", err);
        await postReadResponse(requestId!, readId, {
          success: false,
          error: err instanceof Error ? err.message : "Unknown error",
        });
        return "get_workbook_structure (failed)";
      }
    }

    case "get_sheet_summary": {
      const targetSheet = op.sheet as string;
      const readId = op.read_id as string;
      if (!validateReadOp("get_sheet_summary", requestId, readId)) break;
      try {
        const summary = await getSheetSummary(targetSheet);
        await postReadResponse(requestId!, readId, { success: true, data: summary });
        return `Sheet "${targetSheet}": ${summary.row_count} rows, ${summary.headers.length} cols`;
      } catch (err) {
        console.error("[executeOperation] get_sheet_summary failed:", err);
        await postReadResponse(requestId!, readId, {
          success: false,
          error: err instanceof Error ? err.message : "Unknown error",
        });
        return `get_sheet_summary "${targetSheet}" (failed)`;
      }
    }

    case "find_columns_by_header": {
      const pattern = op.pattern as string;
      const readId = op.read_id as string;
      if (!validateReadOp("find_columns_by_header", requestId, readId)) break;
      try {
        const matches = await findColumnsByHeader(pattern);
        await postReadResponse(requestId!, readId, { success: true, data: matches });
        return `Found ${matches.length} columns matching "${pattern}"`;
      } catch (err) {
        console.error("[executeOperation] find_columns_by_header failed:", err);
        await postReadResponse(requestId!, readId, {
          success: false,
          error: err instanceof Error ? err.message : "Unknown error",
        });
        return `find_columns_by_header "${pattern}" (failed)`;
      }
    }

    case "write_cells":
    case "format_range": {
      const writeReadId = op.read_id as string | undefined;
      const ops = (op.operations || []) as CellOperation[];
      try {
        if (ops.length > 0 && sheet) {
          await writeCells(ops, sheet);
          changedSheets.add(sheet);
        } else if (ops.length > 0 && !sheet) {
          throw new Error(`Write operation skipped: no sheet name specified.`);
        }
        if (writeReadId && requestId) {
          await postReadResponse(requestId, writeReadId, { success: true });
        }
      } catch (err) {
        if (writeReadId && requestId) {
          await postReadResponse(requestId, writeReadId, {
            success: false,
            error: err instanceof Error ? err.message : "Failed to write cells",
          });
        } else {
          throw err;
        }
      }
      break;
    }
    case "clear_range":
      await clearRange(sheet || "", op.range as string, !!op.clear_format);
      break;
    case "copy_range": {
      const copyReadId = op.read_id as string | undefined;
      try {
        await copyRange(
          op.source_sheet as string,
          op.source_range as string,
          op.dest_sheet as string,
          op.dest_start_cell as string,
          (op.mode as string) || "all",
          (op.dest_end_cell as string) || ""
        );
        if (op.dest_sheet) changedSheets.add(op.dest_sheet as string);
        if (copyReadId && requestId) {
          // Report actual destination dimensions for confirmed writes.
          // Parse dest range to compute row/col counts for the agent.
          let rows = 1, cols = 1;
          try {
            const destEnd = (op.dest_end_cell as string) || "";
            if (destEnd) {
              const startMatch = (op.dest_start_cell as string).match(/^([A-Z]+)(\d+)$/i);
              const endMatch = destEnd.match(/^([A-Z]+)(\d+)$/i);
              if (startMatch && endMatch) {
                rows = parseInt(endMatch[2], 10) - parseInt(startMatch[2], 10) + 1;
                // Column count from source range
                const srcMatch = (op.source_range as string).match(/([A-Z]+)\d+:([A-Z]+)\d+/i);
                if (srcMatch) {
                  const colToNum = (c: string) => {
                    let n = 0;
                    for (const ch of c.toUpperCase()) n = n * 26 + ch.charCodeAt(0) - 64;
                    return n;
                  };
                  cols = colToNum(srcMatch[2]) - colToNum(srcMatch[1]) + 1;
                }
              }
            }
          } catch { /* best effort dimension reporting */ }
          await postReadResponse(requestId, copyReadId, { success: true, data: { rows, cols } });
        }
      } catch (err) {
        if (copyReadId && requestId) {
          await postReadResponse(requestId, copyReadId, {
            success: false,
            error: err instanceof Error ? err.message : "Failed to copy range",
          });
        } else {
          throw err;
        }
      }
      break;
    }

    case "insert_rows":
      await insertRows(sheet || "", op.start_row as number, (op.count as number) || 1);
      break;
    case "delete_rows":
      await deleteRows(sheet || "", op.start_row as number, (op.count as number) || 1);
      break;
    case "autofit_columns":
      await autoFitColumns(op.columns as string[], sheet);
      break;
    case "set_column_widths":
      await setColumnWidths(op.widths as Record<string, number>, sheet);
      break;
    case "freeze_panes":
      await freezePanes(op.cell as string, sheet);
      break;

    case "structure_hide":
      if (op.target === "rows") {
        await hideRows(sheet || "", op.start as number, (op.count as number) || 1);
      } else {
        await hideColumns(sheet || "", op.start as number, (op.count as number) || 1);
      }
      break;
    case "structure_unhide":
      if (op.target === "rows") {
        await unhideRows(sheet || "", op.start as number, (op.count as number) || 1);
      } else {
        await unhideColumns(sheet || "", op.start as number, (op.count as number) || 1);
      }
      break;
    case "structure_insert":
      if (op.target === "rows") {
        await insertRows(sheet || "", op.start as number, (op.count as number) || 1);
      }
      break;
    case "structure_delete":
      if (op.target === "rows") {
        await deleteRows(sheet || "", op.start as number, (op.count as number) || 1);
      }
      break;
    case "structure_set_height":
      if (op.target === "rows" && op.size) {
        const heights: Record<string, number> = {};
        const start = op.start as number;
        const count = (op.count as number) || 1;
        for (let i = 0; i < count; i++) {
          heights[String(start + i)] = op.size as number;
        }
        await setRowHeights(heights, sheet);
      }
      break;

    case "create_chart":
      await createChart({
        sheetName: sheet || "",
        dataRange: op.data_range as string,
        chartType: op.chart_type as string,
        title: op.title as string,
        top: op.top as number,
        left: op.left as number,
        width: op.width as number,
        height: op.height as number,
        yAxisMin: op.y_axis_min as number,
        yAxisMax: op.y_axis_max as number,
      });
      break;

    case "create_table":
      await addTable(op.table as TableSpec, sheet);
      break;
    case "add_conditional_format":
      await addConditionalFormat(op.rules as ConditionalFormatRule[], sheet);
      break;
    case "add_data_validation":
      await addDataValidation(op.validations as DataValidationSpec[], sheet);
      break;
    case "add_named_range":
      await addNamedRanges(op.named_ranges as NamedRangeSpec[]);
      break;

    case "sort_range":
      await sortRange(op.sort as SortSpec, sheet);
      break;

    case "create_scenario_table":
      await createScenarioTable(op, changedSheets);
      break;

    case "auto_filter":
      await applyAutoFilter(
        sheet || "",
        op.filter_action as string,
        op.range as string | undefined,
        op.column_index as number | undefined,
        op.criteria as Record<string, unknown> | undefined
      );
      break;

    case "sheet_config": {
      const applied = await configureSheet(sheet || "", {
        tab_color: op.tab_color as string | undefined,
        protect: op.protect as boolean | undefined,
        protect_password: op.protect_password as string | undefined,
        print_area: op.print_area as string | undefined,
        orientation: op.orientation as string | undefined,
        fit_to_page: op.fit_to_page as boolean | undefined,
        show_gridlines: op.show_gridlines as boolean | undefined,
        zoom: op.zoom as number | undefined,
      });
      return `Sheet config updated on ${sheet}: ${applied.join(", ")}.`;
    }

    default:
      console.warn(`[executeOperation] Unknown action: ${action}`);
      throw new Error(`Unknown Excel action: ${action}. This operation was skipped.`);
  }
}

// ─── Post-Write Step Actions (Legacy, plan-mode) ─────────────────────────────

export async function applyPostWriteActions(
  step: AgentStep,
  addMessage: (role: "user" | "agent" | "system" | "plan", text: string) => void
): Promise<void> {
  const safe = async (label: string, fn: () => Promise<void>) => {
    try {
      await fn();
    } catch (err) {
      const msg = friendlyError(err);
      if (msg) addMessage("system", `${label} failed: ${msg}`);
    }
  };

  if (step.rename_sheet) {
    await safe("Rename sheet", () => renameSheet(step.sheet, step.rename_sheet!));
  }

  if (step.column_widths) {
    await safe("Column widths", () => setColumnWidths(step.column_widths!, step.sheet));
  }

  if (step.row_heights) {
    await safe("Row heights", () => setRowHeights(step.row_heights!, step.sheet));
  }

  if (step.autofit_columns && step.autofit_columns.length > 0) {
    await safe("Autofit columns", () => autoFitColumns(step.autofit_columns!, step.sheet));
  }

  if (step.freeze_panes) {
    await safe("Freeze panes", () => freezePanes(step.freeze_panes!, step.sheet));
  }

  if (step.conditional_formats && step.conditional_formats.length > 0) {
    await safe("Conditional formatting", () =>
      addConditionalFormat(step.conditional_formats!, step.sheet)
    );
  }

  if (step.named_ranges && step.named_ranges.length > 0) {
    await safe("Named ranges", () => addNamedRanges(step.named_ranges!));
  }

  if (step.data_validations && step.data_validations.length > 0) {
    await safe("Data validation", () =>
      addDataValidation(step.data_validations!, step.sheet)
    );
  }

  if (step.table) {
    await safe("Create table", () => addTable(step.table!, step.sheet));
  }

  if (step.sort) {
    await safe("Sort range", () => sortRange(step.sort!, step.sheet));
  }

  if (step.protect) {
    const pw = typeof step.protect === "object" ? step.protect.password : undefined;
    await safe("Protect sheet", () => protectSheet(step.sheet, pw));
  }

  if (step.chart) {
    await safe(`Chart: ${step.chart.title || "Untitled"}`, () =>
      createChart({
        sheetName: step.sheet,
        dataRange: step.chart!.data_range,
        chartType: step.chart!.chart_type,
        title: step.chart!.title,
        targetSheet: step.chart!.target_sheet,
        left: step.chart!.left,
        top: step.chart!.top,
        width: step.chart!.width,
        height: step.chart!.height,
      })
    );
  }
}
