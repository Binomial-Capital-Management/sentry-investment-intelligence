/**
 * Type definitions for SEC filings components
 */

export interface Filing {
  cik: string;
  accessionNumber: string;
  type: string;
  filingDate: string;
  acceptedDate: string;
  link: string;
  description: string;
  selected?: boolean;
}

export interface FilingSource {
  id: string;
  title: string;
  url: string;
  snippet: string;
  domain: string;
  cik: string;
  accessionNumber: string;
  formType: string;
  filingDate: string;
}

export interface TickerResult {
  symbol: string;
  name: string;
  exchange: string;
}

export interface MarkdownPage {
  page: number;
  content: string;
}

export type ViewMode = 'markdown' | 'html';

// Earnings call transcript types
export interface Transcript {
  symbol: string;
  year: number;
  quarter: number;
  date: string;
  selected?: boolean;
}

export interface TranscriptContent {
  symbol: string;
  year: number;
  quarter: number;
  date: string;
  content: string;
}

// 13F Institutional holdings types
export interface InstitutionResult {
  cik: string;
  name: string;
}

export interface InstitutionFiling {
  date: string;
  filingDate: string;
  selected?: boolean;
  link?: string;       // SEC index page URL  
  finalLink?: string;  // SEC XML holdings file URL
}

export interface Holding {
  symbol: string;
  securityName: string;
  shares: number;
  value: number;
  weight: number;
  titleOfClass: string;
  cusip: string;
}
