function escapeHtml(str: string): string {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function highlightValueInline(value: unknown): string {
  if (value === null) {
    return '<span class="json-boolean">null</span>';
  }
  if (typeof value === "boolean") {
    return `<span class="json-boolean">${value}</span>`;
  }
  if (typeof value === "number") {
    return `<span class="json-number">${value}</span>`;
  }
  if (typeof value === "string") {
    return `<span class="json-string">"${escapeHtml(value)}"</span>`;
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return "[]";
    const items = value.map((item) => highlightValueInline(item));
    return `[${items.join(", ")}]`;
  }
  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>);
    if (entries.length === 0) return "{}";
    const pairs = entries.map(([key, val]) => {
      return `<span class="json-key">"${escapeHtml(key)}"</span>: ${highlightValueInline(val)}`;
    });
    return `{${pairs.join(", ")}}`;
  }
  return String(value);
}

function highlightValue(value: unknown, indent: number): string {
  const spaces = "  ".repeat(indent);

  if (value === null) {
    return '<span class="json-boolean">null</span>';
  }
  if (typeof value === "boolean") {
    return `<span class="json-boolean">${value}</span>`;
  }
  if (typeof value === "number") {
    return `<span class="json-number">${value}</span>`;
  }
  if (typeof value === "string") {
    return `<span class="json-string">"${escapeHtml(value)}"</span>`;
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return "[]";
    const items = value.map((item) => highlightValueInline(item));
    return `[${items.join(", ")}]`;
  }
  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>);
    if (entries.length === 0) return "{}";
    const lines = entries.map(([key, val]) => {
      return `${spaces}  <span class="json-key">"${escapeHtml(key)}"</span>: ${highlightValue(val, indent + 1)}`;
    });
    return `{\n${lines.join(",\n")}\n${spaces}}`;
  }
  return String(value);
}

export function formatJsonWithSyntax(obj: unknown): string {
  try {
    return highlightValue(obj, 0);
  } catch {
    return escapeHtml(JSON.stringify(obj, null, 2));
  }
}

export function parseAndFormatJson(jsonString: string): string {
  try {
    const parsed = JSON.parse(jsonString);
    return formatJsonWithSyntax(parsed);
  } catch {
    return escapeHtml(jsonString);
  }
}
