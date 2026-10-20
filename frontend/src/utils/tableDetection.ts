/**
 * Auto-detection utilities for Excel/CSV table structure
 * OpenAI-inspired intelligent defaults with confidence scoring
 */

export interface DetectionResult {
  headers: {
    rows: number[];
    confidence: number;
    reason: string;
  };
  identifiers: {
    columns: number[];
    confidence: number;
    reasons: Map<number, string>;
  };
  dataRegion: {
    startRow: number;
    endRow: number;
    startCol: number;
    endCol: number;
    confidence: number;
  };
}

/**
 * Main auto-detection function
 * Analyzes raw data and returns intelligent defaults
 */
export function autoDetectStructure(rawData: any[][]): DetectionResult {
  if (!rawData || rawData.length === 0) {
    return {
      headers: { rows: [], confidence: 0, reason: 'No data' },
      identifiers: { columns: [], confidence: 0, reasons: new Map() },
      dataRegion: { startRow: 0, endRow: 0, startCol: 0, endCol: 0, confidence: 0 },
    };
  }

  const headers = detectHeaders(rawData);
  const identifiers = detectIdentifiers(rawData, headers.rows);
  const dataRegion = detectDataRegion(rawData, headers.rows);

  return { headers, identifiers, dataRegion };
}

/**
 * Detect header rows using multiple heuristics
 */
function detectHeaders(rawData: any[][]) {
  let confidence = 0;
  const reasons: string[] = [];

  if (rawData.length === 0) {
    return { rows: [], confidence: 0, reason: 'No data' };
  }

  const firstRow = rawData[0];

  // Heuristic 1: First row is text, subsequent rows have numbers
  const isTextRow = firstRow.every(cell =>
    typeof cell === 'string' || cell === null || cell === '',
  );

  const sampleRows = rawData.slice(1, Math.min(11, rawData.length));
  const hasNumericData = sampleRows.some(row =>
    row.some(cell => typeof cell === 'number'),
  );

  if (isTextRow && hasNumericData) {
    confidence += 0.5;
    reasons.push('First row contains text, data rows contain numbers');
  } else if (isTextRow) {
    confidence += 0.3;
    reasons.push('First row contains text');
  }

  // Heuristic 2: Look for common header patterns
  const headerPatterns = /\b(name|id|date|amount|price|quantity|status|type|category|description|revenue|profit|customer|product|email|phone|address|city|state|country|zip|code)\b/i;
  const matchesPattern = firstRow.some(cell =>
    headerPatterns.test(String(cell || '')),
  );

  if (matchesPattern) {
    confidence += 0.3;
    reasons.push('Contains common header keywords');
  }

  // Heuristic 3: Check for mixed case or formatted text (likely headers)
  const hasFormattedText = firstRow.some(cell => {
    const str = String(cell || '');
    return /[A-Z].*[a-z]|[a-z].*[A-Z]/.test(str); // Mixed case
  });

  if (hasFormattedText) {
    confidence += 0.2;
    reasons.push('Contains formatted text');
  }

  // Cap confidence at 1.0
  confidence = Math.min(confidence, 1.0);

  return {
    rows: [0],
    confidence,
    reason: reasons.length > 0 ? reasons.join('. ') : 'Default to first row',
  };
}

/**
 * Detect identifier columns using scoring algorithm
 */
function detectIdentifiers(rawData: any[][], headerRows: number[]) {
  const scores: Array<{col: number, score: number, reasons: string[]}> = [];

  if (rawData.length === 0 || headerRows.length === 0) {
    return { columns: [], confidence: 0, reasons: new Map() };
  }

  const dataStartRow = Math.max(...headerRows) + 1;
  const dataRows = rawData.slice(dataStartRow);

  if (dataRows.length === 0) {
    return { columns: [], confidence: 0, reasons: new Map() };
  }

  for (let col = 0; col < rawData[0].length; col++) {
    let score = 0;
    const reasons: string[] = [];

    // Get header text and values
    const headerText = String(rawData[headerRows[0]]?.[col] || '').toLowerCase();
    const values = dataRows.map(row => row[col]).filter(v => v !== null && v !== '');

    if (values.length === 0) continue;

    // Score 1: Column name contains id/name/code/key (40 points)
    if (/\b(id|identifier|key|code)\b/.test(headerText)) {
      score += 40;
      reasons.push('Column name suggests identifier');
    } else if (/\b(name|title)\b/.test(headerText)) {
      score += 30;
      reasons.push('Column name suggests name/title');
    }

    // Score 2: Values are unique (30 points)
    const uniqueCount = new Set(values.map(v => String(v))).size;
    const uniqueRatio = uniqueCount / values.length;
    if (uniqueRatio > 0.95) {
      score += 30;
      reasons.push(`${(uniqueRatio * 100).toFixed(0)}% unique values`);
    } else if (uniqueRatio > 0.8) {
      score += 20;
      reasons.push(`${(uniqueRatio * 100).toFixed(0)}% unique values`);
    } else if (uniqueRatio > 0.6) {
      score += 10;
      reasons.push(`${(uniqueRatio * 100).toFixed(0)}% unique values`);
    }

    // Score 3: No null/empty values (15 points)
    const nullCount = dataRows.filter(row => row[col] === null || row[col] === '').length;
    if (nullCount === 0) {
      score += 15;
      reasons.push('No missing values');
    } else if (nullCount < dataRows.length * 0.1) {
      score += 10;
      reasons.push('Few missing values');
    }

    // Score 4: Leftmost column (10 points)
    if (col === 0) {
      score += 10;
      reasons.push('First column');
    } else if (col === 1) {
      score += 5;
      reasons.push('Second column');
    }

    // Score 5: Non-numeric values preferred (5 points)
    const numericCount = values.filter(v => typeof v === 'number').length;
    if (numericCount < values.length * 0.3) {
      score += 5;
      reasons.push('Mostly text-based');
    }

    scores.push({ col, score, reasons });
  }

  // Return columns with score > 50
  const identifierCols = scores.filter(s => s.score > 50);

  // Calculate overall confidence
  let overallConfidence = 0;
  if (identifierCols.length > 0) {
    const avgScore = identifierCols.reduce((sum, s) => sum + s.score, 0) / identifierCols.length;
    overallConfidence = Math.min(avgScore / 100, 1.0);
  }

  // Build reasons map
  const reasonsMap = new Map(
    identifierCols.map(s => [s.col, s.reasons.join(', ')]),
  );

  return {
    columns: identifierCols.map(s => s.col),
    confidence: overallConfidence,
    reasons: reasonsMap,
  };
}

/**
 * Detect data region (area containing actual data)
 */
function detectDataRegion(rawData: any[][], headerRows: number[]) {
  if (rawData.length === 0) {
    return {
      startRow: 0,
      endRow: 0,
      startCol: 0,
      endCol: 0,
      confidence: 0,
    };
  }

  const startRow = headerRows.length > 0 ? Math.max(...headerRows) + 1 : 0;
  const endRow = rawData.length - 1;
  const startCol = 0;
  const endCol = rawData[0]?.length - 1 || 0;

  // Calculate confidence based on data density
  let totalCells = 0;
  let filledCells = 0;

  for (let r = startRow; r <= endRow; r++) {
    for (let c = startCol; c <= endCol; c++) {
      totalCells++;
      if (rawData[r]?.[c] !== null && rawData[r]?.[c] !== '') {
        filledCells++;
      }
    }
  }

  const density = totalCells > 0 ? filledCells / totalCells : 0;
  const confidence = Math.min(density + 0.1, 1.0); // Add 0.1 base confidence

  return {
    startRow,
    endRow,
    startCol,
    endCol,
    confidence,
  };
}

/**
 * Helper: Calculate overall detection confidence
 */
export function calculateOverallConfidence(result: DetectionResult): number {
  return (
    result.headers.confidence * 0.4 +
    result.identifiers.confidence * 0.3 +
    result.dataRegion.confidence * 0.3
  );
}
