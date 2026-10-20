/**
 * useSelectionContext — Track Excel selection for context injection
 *
 * Listens to selection changes via Office.js and returns the current selection
 * with range address, sheet name, dimensions, and a preview of values.
 */

import { useState, useEffect, useCallback, useRef } from "react";

/* global Excel */

export interface SelectionContext {
  range: string;
  sheet: string;
  rowCount: number;
  colCount: number;
  values: (string | number | boolean | null)[][];
  headers: (string | number | boolean | null)[];
}

interface UseSelectionContextReturn {
  selection: SelectionContext | null;
  clearSelection: () => void;
  refreshSelection: () => Promise<void>;
}

const MAX_PREVIEW_ROWS = 50;
const MAX_PREVIEW_COLS = 20;
const DEBOUNCE_MS = 50;

export function useSelectionContext(): UseSelectionContextReturn {
  const [selection, setSelection] = useState<SelectionContext | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const handlerRef = useRef<((args: Excel.SelectionChangedEventArgs) => Promise<void>) | null>(null);

  const readSelection = useCallback(async (): Promise<SelectionContext | null> => {
    try {
      return await Excel.run(async (ctx) => {
        const range = ctx.workbook.getSelectedRange();
        range.load(["address", "rowCount", "columnCount", "values", "worksheet/name"]);
        await ctx.sync();

        const fullAddress = range.address;
        const sheetName = range.worksheet.name;
        const rowCount = range.rowCount;
        const colCount = range.columnCount;

        // Extract just the range part (e.g., "Sheet1!A1:B10" -> "A1:B10")
        const rangeOnly = fullAddress.includes("!")
          ? fullAddress.split("!")[1]
          : fullAddress;

        // Limit preview size
        const previewRows = Math.min(rowCount, MAX_PREVIEW_ROWS);
        const previewCols = Math.min(colCount, MAX_PREVIEW_COLS);
        const values = range.values
          .slice(0, previewRows)
          .map((row) => row.slice(0, previewCols));

        // First row as headers
        const headers = values.length > 0 ? values[0] : [];

        return {
          range: rangeOnly,
          sheet: sheetName,
          rowCount,
          colCount,
          values,
          headers,
        };
      });
    } catch (err) {
      console.warn("[useSelectionContext] Failed to read selection:", err);
      return null;
    }
  }, []);

  const refreshSelection = useCallback(async () => {
    const sel = await readSelection();
    setSelection(sel);
  }, [readSelection]);

  const clearSelection = useCallback(() => {
    setSelection(null);
  }, []);

  useEffect(() => {
    let mounted = true;

    async function setup() {
      try {
        await Excel.run(async (ctx) => {
          const handler = async (): Promise<void> => {
            // Debounce rapid selection changes
            if (debounceRef.current) {
              clearTimeout(debounceRef.current);
            }
            debounceRef.current = setTimeout(async () => {
              if (!mounted) return;
              const sel = await readSelection();
              if (mounted) {
                setSelection(sel);
              }
            }, DEBOUNCE_MS);
          };

          handlerRef.current = handler;
          ctx.workbook.onSelectionChanged.add(handler);
          await ctx.sync();
        });

        // Read initial selection
        if (mounted) {
          const initial = await readSelection();
          if (mounted) {
            setSelection(initial);
          }
        }
      } catch (err) {
        console.warn("[useSelectionContext] Failed to setup selection listener:", err);
      }
    }

    setup();

    return () => {
      mounted = false;
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
      // Remove event handler
      if (handlerRef.current) {
        Excel.run(async (ctx) => {
          ctx.workbook.onSelectionChanged.remove(handlerRef.current!);
          await ctx.sync();
        }).catch(() => {
          // Ignore cleanup errors
        });
      }
    };
  }, [readSelection]);

  return {
    selection,
    clearSelection,
    refreshSelection,
  };
}
