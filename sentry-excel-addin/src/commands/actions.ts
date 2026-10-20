/**
 * Office.js action functions — the agent's hands inside Excel.
 *
 * Each function takes a JSON string message (required by Office.actions.associate)
 * and returns a string result. The shared runtime keeps these alive while the
 * task pane is open.
 */

/* global Office, Excel */

Office.onReady(() => {
  // Runtime is ready
});

// -- Write Operations --

async function writeCells(message: string): Promise<string> {
  const { operations } = JSON.parse(message) as {
    operations: Array<{
      range: string;
      values?: (string | number | null)[][];
      formulas?: (string | null)[][];
      format?: {
        bold?: boolean;
        fill?: string;
        font_color?: string;
        number_format?: string;
      };
    }>;
  };

  let applied = 0;
  await Excel.run(async (ctx) => {
    const sheet = ctx.workbook.worksheets.getActiveWorksheet();

    const limit = Math.min(operations.length, 50); // bounded
    for (let i = 0; i < limit; i++) {
      const op = operations[i];
      const range = sheet.getRange(op.range);

      if (op.values) range.values = op.values;
      if (op.formulas) range.formulas = op.formulas;

      if (op.format) {
        if (op.format.bold) range.format.font.bold = true;
        if (op.format.fill) range.format.fill.color = op.format.fill;
        if (op.format.font_color) range.format.font.color = op.format.font_color;
        if (op.format.number_format) {
          range.numberFormat = op.format.number_format as unknown as string[][];
        }
      }
      applied++;
    }

    await ctx.sync();
  });

  return JSON.stringify({ applied });
}

// -- Read Operations --

async function readRange(message: string): Promise<string> {
  const { range: addr, sheet: sheetName } = JSON.parse(message) as {
    range: string;
    sheet?: string;
  };

  let result: { values: unknown[][]; formulas: unknown[][] } | null = null;

  await Excel.run(async (ctx) => {
    const sheet = sheetName
      ? ctx.workbook.worksheets.getItem(sheetName)
      : ctx.workbook.worksheets.getActiveWorksheet();
    const range = sheet.getRange(addr);
    range.load(["values", "formulas", "numberFormat"]);
    await ctx.sync();
    result = { values: range.values, formulas: range.formulas };
  });

  return JSON.stringify(result);
}

async function readWorkbookContext(): Promise<string> {
  const sheets: Record<
    string,
    { values: unknown[][]; formulas: unknown[][]; rows: number; cols: number }
  > = {};

  await Excel.run(async (ctx) => {
    const worksheets = ctx.workbook.worksheets;
    worksheets.load("items/name");
    await ctx.sync();

    const sheetLimit = Math.min(worksheets.items.length, 100); // bounded
    for (let i = 0; i < sheetLimit; i++) {
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

  return JSON.stringify({ sheets });
}

async function readSheet(message: string): Promise<string> {
  const { sheet: sheetName } = JSON.parse(message) as { sheet: string };

  let result: { values: unknown[][]; formulas: unknown[][]; rows: number; cols: number } | null =
    null;

  await Excel.run(async (ctx) => {
    const ws = ctx.workbook.worksheets.getItem(sheetName);
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

  return JSON.stringify(result);
}

// -- Sheet Operations --

async function createSheet(message: string): Promise<string> {
  const { name } = JSON.parse(message) as { name: string };

  await Excel.run(async (ctx) => {
    const ws = ctx.workbook.worksheets.add(name);
    ws.activate();
    await ctx.sync();
  });

  return JSON.stringify({ created: name });
}

// -- Chart Operations --

async function createChart(message: string): Promise<string> {
  const {
    data_range: dataRange,
    chart_type: chartType,
    title,
  } = JSON.parse(message) as {
    data_range: string;
    chart_type?: string;
    title?: string;
  };

  await Excel.run(async (ctx) => {
    const sheet = ctx.workbook.worksheets.getActiveWorksheet();
    const range = sheet.getRange(dataRange);
    const chart = sheet.charts.add(
      (chartType as Excel.ChartType) || Excel.ChartType.columnClustered,
      range,
      Excel.ChartSeriesBy.auto
    );
    if (title) chart.title.text = title;
    chart.setPosition("H2", "P15");
    await ctx.sync();
  });

  return JSON.stringify({ chart: title || "Untitled" });
}

// -- Format Operations --

async function formatRange(message: string): Promise<string> {
  const {
    range: addr,
    bold,
    fill,
    font_color: fontColor,
    number_format: numFmt,
    borders,
  } = JSON.parse(message) as {
    range: string;
    bold?: boolean;
    fill?: string;
    font_color?: string;
    number_format?: string;
    borders?: boolean;
  };

  await Excel.run(async (ctx) => {
    const sheet = ctx.workbook.worksheets.getActiveWorksheet();
    const range = sheet.getRange(addr);

    if (bold !== undefined) range.format.font.bold = bold;
    if (fill) range.format.fill.color = fill;
    if (fontColor) range.format.font.color = fontColor;
    if (numFmt) range.numberFormat = numFmt as unknown as string[][];
    if (borders) {
      range.format.borders.getItem(Excel.BorderIndex.edgeTop).style =
        Excel.BorderLineStyle.continuous;
      range.format.borders.getItem(Excel.BorderIndex.edgeBottom).style =
        Excel.BorderLineStyle.continuous;
    }

    await ctx.sync();
  });

  return JSON.stringify({ formatted: addr });
}

// -- Register all actions --

Office.actions.associate("WriteCells", writeCells);
Office.actions.associate("ReadRange", readRange);
Office.actions.associate("ReadWorkbookContext", readWorkbookContext);
Office.actions.associate("ReadSheet", readSheet);
Office.actions.associate("CreateSheet", createSheet);
Office.actions.associate("CreateChart", createChart);
Office.actions.associate("FormatRange", formatRange);
