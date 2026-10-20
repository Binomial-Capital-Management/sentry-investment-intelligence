/**
 * VBA syntax highlighting for code blocks.
 * Returns HTML string with span-wrapped tokens.
 */

export function highlightVba(code: string): string {
  const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const lines = code.split("\n");
  return lines.map((raw) => {
    const line = esc(raw);
    const commentIdx = line.indexOf("'");
    const before = commentIdx >= 0 ? line.slice(0, commentIdx) : line;
    const comment = commentIdx >= 0 ? line.slice(commentIdx) : "";
    const kw = /\b(Sub|End Sub|Function|End Function|Public|Private|Dim|As|Set|If|Then|Else|ElseIf|End If|For|Each|In|Next|Do|Loop|While|Wend|With|End With|Select Case|Case|End Select|GoTo|On Error|Resume|Exit|ByVal|ByRef|Optional|Variant|String|Double|Long|Integer|Boolean|Object|Range|Worksheet|Workbook|Nothing|True|False|Not|And|Or|New|Let|Call|Property|Get|Me|Is|Like|Mod|To|Step)\b/g;
    const strs = /(".*?")/g;
    const nums = /\b(\d+\.?\d*)\b/g;
    let highlighted = before
      .replace(strs, '<span style="color:#059669">$1</span>')
      .replace(kw, '<span style="color:#2563eb;font-weight:600">$1</span>')
      .replace(nums, '<span style="color:#d97706">$1</span>');
    if (comment) {
      highlighted += `<span style="color:#6b7280;font-style:italic">${comment}</span>`;
    }
    return highlighted;
  }).join("\n");
}
