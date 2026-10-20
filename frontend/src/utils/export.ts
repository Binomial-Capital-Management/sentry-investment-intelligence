// Simple utility functions for exporting data

// Convert data to CSV format
export function dataToCSV(data: any[], headers?: string[]): string {
  if (!data || data.length === 0) return '';

  // Auto-detect headers from first object if not provided
  const csvHeaders = headers || Object.keys(data[0]);

  // Create CSV rows
  const rows = data.map(row =>
    csvHeaders.map(header => {
      const value = row[header];
      // Handle values with commas or quotes
      if (typeof value === 'string' && (value.includes(',') || value.includes('"'))) {
        return `"${value.replace(/"/g, '""')}"`;
      }
      return value ?? '';
    }).join(','),
  );

  // Combine headers and rows
  return [csvHeaders.join(','), ...rows].join('\n');
}

// Download CSV file
export function downloadCSV(filename: string, csvContent: string) {
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const link = document.createElement('a');
  const url = URL.createObjectURL(blob);

  link.setAttribute('href', url);
  link.setAttribute('download', filename);
  link.style.display = 'none';

  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);

  URL.revokeObjectURL(url);
}

// Copy text to clipboard
export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch (err) {
    // Fallback for older browsers
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';

    document.body.appendChild(textarea);
    textarea.select();

    try {
      document.execCommand('copy');
      document.body.removeChild(textarea);
      return true;
    } catch {
      document.body.removeChild(textarea);
      return false;
    }
  }
}

// Copy message content with format preservation
export async function copyMessageContent(element: HTMLElement): Promise<boolean> {
  try {
    // Get the HTML content
    const htmlContent = element.innerHTML;

    // Also get plain text version for fallback
    const textContent = element.innerText || element.textContent || '';

    // Try to use the modern Clipboard API with both HTML and text
    if (navigator.clipboard && 'write' in navigator.clipboard) {
      const blob = new Blob([htmlContent], { type: 'text/html' });
      const textBlob = new Blob([textContent], { type: 'text/plain' });

      const clipboardItem = new ClipboardItem({
        'text/html': blob,
        'text/plain': textBlob,
      });

      await navigator.clipboard.write([clipboardItem]);
      return true;
    } else {
      // Fallback to plain text copy
      return await copyToClipboard(textContent);
    }
  } catch (err) {
    console.error('Failed to copy message:', err);
    // Final fallback
    const textContent = element.innerText || element.textContent || '';
    return await copyToClipboard(textContent);
  }
}

// Format data as table for copying
export function formatAsTable(data: any[], headers?: string[]): string {
  if (!data || data.length === 0) return '';

  const tableHeaders = headers || Object.keys(data[0]);
  const rows = data.map(row =>
    tableHeaders.map(header => row[header] ?? '').join('\t'),
  );

  return [tableHeaders.join('\t'), ...rows].join('\n');
}
