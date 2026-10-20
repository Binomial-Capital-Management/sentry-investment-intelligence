/**
 * JSON Syntax Highlighting Utility
 * 
 * Formats JSON objects with Claude-style syntax highlighting colors:
 * - Keys: purple (rgb(111, 66, 193))
 * - Numbers: blue (rgb(0, 92, 197))
 * - Strings: dark blue (rgb(3, 47, 98))
 * - Booleans: teal (rgb(0, 134, 179))
 * - Null: gray
 */

const COLORS = {
  key: "rgb(111, 66, 193)",
  number: "rgb(0, 92, 197)",
  string: "rgb(3, 47, 98)",
  boolean: "rgb(0, 134, 179)",
  null: "rgb(128, 128, 128)",
};

function escapeHtml(str: string): string {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/**
 * Render a value completely inline (no newlines) - used for array contents
 */
function highlightValueInline(value: unknown): string {
  if (value === null) {
    return `<span style="color: ${COLORS.null}">null</span>`;
  }

  if (typeof value === "boolean") {
    return `<span style="color: ${COLORS.boolean}">${value}</span>`;
  }

  if (typeof value === "number") {
    return `<span style="color: ${COLORS.number}">${value}</span>`;
  }

  if (typeof value === "string") {
    return `<span style="color: ${COLORS.string}">"${escapeHtml(value)}"</span>`;
  }

  if (Array.isArray(value)) {
    if (value.length === 0) return "[]";
    const items = value.map((item) => highlightValueInline(item));
    return `[${items.join(", ")}]`;
  }

  if (typeof value === "object") {
    const entries = Object.entries(value);
    if (entries.length === 0) return "{}";
    const pairs = entries.map(([key, val]) => {
      const keySpan = `<span style="color: ${COLORS.key}">"${escapeHtml(key)}"</span>`;
      return `${keySpan}: ${highlightValueInline(val)}`;
    });
    return `{${pairs.join(", ")}}`;
  }

  return String(value);
}

/**
 * Render a value with formatting - only top-level objects get multi-line
 */
function highlightValue(value: unknown, indent: number): string {
  const spaces = "  ".repeat(indent);

  if (value === null) {
    return `<span style="color: ${COLORS.null}">null</span>`;
  }

  if (typeof value === "boolean") {
    return `<span style="color: ${COLORS.boolean}">${value}</span>`;
  }

  if (typeof value === "number") {
    return `<span style="color: ${COLORS.number}">${value}</span>`;
  }

  if (typeof value === "string") {
    return `<span style="color: ${COLORS.string}">"${escapeHtml(value)}"</span>`;
  }

  // Arrays: ALWAYS inline (single horizontal line with scroll)
  if (Array.isArray(value)) {
    if (value.length === 0) return "[]";
    const items = value.map((item) => highlightValueInline(item));
    return `[${items.join(", ")}]`;
  }

  // Objects: multi-line with each key on its own line
  if (typeof value === "object") {
    const entries = Object.entries(value);
    if (entries.length === 0) return "{}";
    const lines = entries.map(([key, val]) => {
      const keySpan = `<span style="color: ${COLORS.key}">"${escapeHtml(key)}"</span>`;
      return `${spaces}  ${keySpan}: ${highlightValue(val, indent + 1)}`;
    });
    return `{\n${lines.join(",\n")}\n${spaces}}`;
  }

  return String(value);
}

/**
 * Format a JSON object or value with Claude-style syntax highlighting.
 * Returns HTML string with inline styles for colors.
 */
export function formatJsonWithSyntax(obj: unknown): string {
  try {
    return highlightValue(obj, 0);
  } catch {
    // Fallback: return plain JSON
    return escapeHtml(JSON.stringify(obj, null, 2));
  }
}

/**
 * Safely parse and format JSON from a string.
 * Returns highlighted HTML or escaped plain text on parse failure.
 */
export function parseAndFormatJson(jsonString: string): string {
  try {
    const parsed = JSON.parse(jsonString);
    return formatJsonWithSyntax(parsed);
  } catch {
    return escapeHtml(jsonString);
  }
}
