import { useMemo } from 'react';
import { TableSelections } from './ExcelPreviewModal';

interface ParsedPreviewProps {
  rawData: any[][];
  selections: TableSelections;
}

export default function ParsedPreview({ rawData, selections }: ParsedPreviewProps) {
  console.log('=== ParsedPreview render ===');
  console.log('selections.identifierCells:', selections.identifierCells);
  console.log('identifierCells size:', selections.identifierCells?.size);
  console.log('identifierCells is Set?:', selections.identifierCells instanceof Set);

  const parsedData = useMemo(() => {
    console.log('=== ParsedPreview useMemo executing ===');
    if (!rawData || rawData.length === 0) return null;

    const { headerCells, identifierCells, dataRegion } = selections;
    console.log('Inside useMemo - identifierCells size:', identifierCells.size);
    console.log('Inside useMemo - identifierCells:', Array.from(identifierCells));

    // Find all rows and columns that have headers
    const headerRowsSet = new Set<number>();
    headerCells.forEach(key => {
      const [row] = key.split(',').map(Number);
      headerRowsSet.add(row);
    });
    const headerRows = Array.from(headerRowsSet).sort((a, b) => a - b);

    // Only parse if dataRegion is explicitly set
    if (!dataRegion) {
      return null; // Don't parse until user selects a data region
    }

    // Find which columns have identifiers
    const identifierColsSet = new Set<number>();
    identifierCells.forEach(key => {
      const [row, col] = key.split(',').map(Number);
      identifierColsSet.add(col);
    });
    const identifierColsArray = Array.from(identifierColsSet).sort((a, b) => a - b);

    // Expand data region to include identifier columns
    let startCol = dataRegion.startCol;
    let endCol = dataRegion.endCol;

    // If there are identifier columns before startCol, include them
    if (identifierColsArray.length > 0 && identifierColsArray[0] < startCol) {
      startCol = identifierColsArray[0];
    }

    // If there are identifier columns after endCol, include them
    if (identifierColsArray.length > 0 && identifierColsArray[identifierColsArray.length - 1] > endCol) {
      endCol = identifierColsArray[identifierColsArray.length - 1];
    }

    const startRow = dataRegion.startRow;
    const endRow = dataRegion.endRow;

    console.log('Data region adjustment:', {
      original: { startCol: dataRegion.startCol, endCol: dataRegion.endCol },
      identifierCols: identifierColsArray,
      adjusted: { startCol, endCol },
    });

    // Build column headers from selected header cells (including identifier columns)
    const headers: string[] = [];
    for (let col = startCol; col <= endCol; col++) {
      const headerParts: string[] = [];
      for (const rowIdx of headerRows) {
        const cellKey = `${rowIdx},${col}`;
        if (headerCells.has(cellKey)) {
          const value = rawData[rowIdx]?.[col];
          if (value) {
            headerParts.push(String(value));
          }
        }
      }
      headers.push(headerParts.length > 0 ? headerParts.join(' / ') : `Column ${col + 1}`);
    }

    // Get data rows (only from data region)
    const dataRows = rawData
      .slice(startRow, endRow + 1)
      .map(row => row.slice(startCol, endCol + 1));

    // Check which columns are identifiers (check if column is in identifierCells)
    const markedHeaders = headers.map((header, colIdx) => {
      const actualCol = startCol + colIdx;
      let isIdentifier = false;

      // Check if ANY cell in this column is marked as identifier
      identifierCells.forEach(cellKey => {
        const [row, col] = cellKey.split(',').map(Number);
        if (col === actualCol) {
          isIdentifier = true;
        }
      });

      console.log(`ParsedPreview - Column ${actualCol} "${header}": isIdentifier=${isIdentifier}, identifierCells size=${identifierCells.size}, first few IDs:`, Array.from(identifierCells).slice(0, 5));
      return { name: header, isIdentifier };
    });

    return { headers: markedHeaders, data: dataRows };
  }, [rawData, selections]);

  if (!parsedData) {
    return (
      <div className="h-full flex items-center justify-center">
        <p className="text-[var(--sentry-gray-500)]">
          {selections.headerCells.size === 0
            ? 'Select headers and drag to select data region'
            : 'Switch to Data mode and drag to select data region'}
        </p>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col p-4">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-sm font-medium text-slate-700">
          {parsedData.data.length} rows × {parsedData.headers.length} columns
        </p>
        <p className="text-xs text-slate-500">
          {parsedData.headers.filter(h => h.isIdentifier).length} identifier column{parsedData.headers.filter(h => h.isIdentifier).length !== 1 ? 's' : ''}
        </p>
      </div>

      <div className="flex-1 overflow-auto border border-slate-300 rounded bg-white">
        <table className="w-full border-collapse">
          <thead className="sticky top-0 bg-slate-100">
            <tr>
              {parsedData.headers.map((header, idx) => (
                <th
                  key={idx}
                  className={`
                    px-3 py-2 text-left text-sm font-semibold border-b-2
                    ${header.isIdentifier
                      ? 'bg-blue-50 border-blue-400'
                      : 'border-slate-300'
                    }
                  `}
                >
                  <div className="flex items-center gap-2">
                    <span>{header.name}</span>
                    {header.isIdentifier && (
                      <span className="inline-flex items-center px-1.5 py-0.5 rounded bg-blue-600 text-white text-[9px] font-semibold">
                        ID
                      </span>
                    )}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {parsedData.data.slice(0, 100).map((row, rowIdx) => (
              <tr key={rowIdx} className="hover:bg-slate-50">
                {row.map((cell: any, colIdx: number) => (
                  <td
                    key={colIdx}
                    className={`
                      px-3 py-2 text-sm border-b border-slate-200
                      ${parsedData.headers[colIdx]?.isIdentifier
                        ? 'font-mono bg-blue-50/70 text-blue-900 font-medium'
                        : ''
                      }
                    `}
                  >
                    {cell?.toString() || ''}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        {parsedData.data.length > 100 && (
          <div className="p-3 text-center text-sm text-slate-600 bg-slate-50 border-t border-slate-300">
            Showing first 100 of {parsedData.data.length} rows
          </div>
        )}
      </div>
    </div>
  );
}
