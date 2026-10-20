/**
 * Utility functions for SEC filings components
 */

import { Filing } from './types';

const logoDevToken = (import.meta as any).env?.VITE_LOGODEV_TOKEN;

/**
 * Get company logo URL
 */
export function getCompanyLogoUrl(symbol: string): string {
  if (!logoDevToken) {
    return `https://logo.clearbit.com/${symbol.toLowerCase()}.com`;
  }
  return `https://img.logo.dev/ticker/${symbol.toUpperCase()}?token=${logoDevToken}`;
}

/**
 * Format date string to MM/DD/YY
 */
export function formatDate(dateStr: string): string {
  if (!dateStr) return '';
  try {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { 
      month: '2-digit', 
      day: '2-digit', 
      year: '2-digit' 
    });
  } catch {
    return dateStr;
  }
}

/**
 * Get period label for financial filings (e.g., "FY 2024", "Q1 2024")
 */
export function getPeriodLabel(filing: Filing): string {
  const type = filing.type?.toUpperCase() || '';
  const year = filing.filingDate?.substring(0, 4) || '';
  const month = parseInt(filing.filingDate?.substring(5, 7) || '0');
  
  if (type.includes('10-K')) {
    return `FY ${month <= 3 ? String(parseInt(year) - 1) : year}`;
  }
  
  if (type.includes('10-Q')) {
    if (month >= 1 && month <= 5) return `Q1 ${year}`;
    if (month >= 4 && month <= 8) return `Q2 ${year}`;
    if (month >= 7 && month <= 11) return `Q3 ${year}`;
    return `Q4 ${year}`;
  }
  
  return '';
}

/**
 * Format period end date for financial filings
 */
export function formatPeriodEnd(filing: Filing): string {
  const type = filing.type?.toUpperCase() || '';
  const year = filing.filingDate?.substring(0, 4) || '';
  const month = parseInt(filing.filingDate?.substring(5, 7) || '0');
  
  if (type.includes('10-K')) {
    return `12/31/${(month <= 3 ? String(parseInt(year) - 1) : year).slice(-2)}`;
  }
  
  if (type.includes('10-Q')) {
    if (month >= 1 && month <= 5) return `03/31/${year.slice(-2)}`;
    if (month >= 4 && month <= 8) return `06/30/${year.slice(-2)}`;
    if (month >= 7 && month <= 11) return `09/30/${year.slice(-2)}`;
    return `12/31/${year.slice(-2)}`;
  }
  
  return '';
}

/**
 * Group filings by category
 */
export function groupFilings(filings: Filing[]) {
  const mostRecent = filings.filter(f => {
    const t = f.type?.toUpperCase() || '';
    return t.includes('8-K') || t.includes('EX-') || t.includes('424');
  }).slice(0, 10);
  
  const financials = filings.filter(f => {
    const t = f.type?.toUpperCase() || '';
    return t.includes('10-K') || t.includes('10-Q');
  }).slice(0, 20);
  
  const usedIds = new Set([...mostRecent, ...financials].map(f => f.accessionNumber));
  const other = filings.filter(f => !usedIds.has(f.accessionNumber)).slice(0, 20);
  
  return { mostRecent, financials, other };
}
