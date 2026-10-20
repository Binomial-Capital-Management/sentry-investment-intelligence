/**
 * Workbook hashing utilities.
 *
 * - Identity hash: persistent UUID stored in workbook custom properties
 * - Per-sheet content hashes: detect which sheets changed (cheap — samples first rows)
 * - Combined content hash: single string for backend diff check
 */

/* global Excel */

// ─── Custom property key for persistent workbook identity ───

const WORKBOOK_ID_KEY = "SentryWorkbookId";

// ─── Shared SHA-256 helper ───

async function sha256(input: string): Promise<string> {
  const data = new TextEncoder().encode(input);
  const buf = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(buf))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("")
    .slice(0, 32);
}

// ─── Identity hash (persistent across all workbook modifications) ───

export async function getWorkbookHash(): Promise<string> {
  let workbookId = "";

  await Excel.run(async (ctx) => {
    const customProps = ctx.workbook.properties.custom;
    const existing = customProps.getItemOrNullObject(WORKBOOK_ID_KEY);
    existing.load("value");
    await ctx.sync();

    if (!existing.isNullObject) {
      workbookId = existing.value;
    } else {
      workbookId = crypto.randomUUID();
      customProps.add(WORKBOOK_ID_KEY, workbookId);
      await ctx.sync();
    }
  });

  return workbookId;
}

// ─── Per-sheet content hashes ───

/**
 * Returns a hash for each sheet based on a sample of its content.
 * Cheap: reads only the first 5 rows × 10 columns per sheet.
 * Used to detect which specific sheets changed since last index.
 */
export async function getPerSheetHashes(): Promise<Record<string, string>> {
  const samples: Record<string, string> = {};

  await Excel.run(async (ctx) => {
    const sheets = ctx.workbook.worksheets;
    sheets.load("items/name");
    await ctx.sync();

    const limit = Math.min(sheets.items.length, 100);
    for (let i = 0; i < limit; i++) {
      const ws = sheets.items[i];
      const used = ws.getUsedRangeOrNullObject(true); // valuesOnly: ignore formatting-only cells
      used.load(["rowCount", "columnCount"]);
      await ctx.sync();

      if (used.isNullObject) {
        samples[ws.name] = "empty";
        continue;
      }

      const rows = Math.min(used.rowCount, 5);
      const cols = Math.min(used.columnCount, 10);
      const sampleRange = ws.getRangeByIndexes(0, 0, rows, cols);
      sampleRange.load("values");
      await ctx.sync();

      samples[ws.name] = JSON.stringify(sampleRange.values);
    }
  });

  // Hash each sheet's sample
  const hashes: Record<string, string> = {};
  for (const [name, sample] of Object.entries(samples)) {
    hashes[name] = await sha256(`${name}:${sample}`);
  }
  return hashes;
}

// ─── Combined content hash (for backend diff endpoint) ───

export async function getContentHash(): Promise<string> {
  const perSheet = await getPerSheetHashes();
  const combined = Object.entries(perSheet)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([name, hash]) => `${name}=${hash}`)
    .join("|");
  return sha256(combined);
}
