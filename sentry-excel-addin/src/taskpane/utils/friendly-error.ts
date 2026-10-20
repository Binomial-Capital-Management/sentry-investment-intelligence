/**
 * Converts raw technical errors into readable messages for the chat panel.
 * Matches common Office.js, network, and agent error patterns.
 */
export function friendlyError(raw: unknown): string {
  const msg = raw instanceof Error ? raw.message : String(raw ?? "Unknown error");

  // ── Office.js / Excel errors ──
  if (/undefined is not an object/i.test(msg) || /cannot read propert/i.test(msg) || /null is not an object/i.test(msg))
    return "Excel couldn't complete that operation — it may have received unexpected data.";
  if (/range address.*invalid|invalid.*range/i.test(msg))
    return "The cell range was invalid. Check that the data fits the target area.";
  if (/itemnotfound|item not found/i.test(msg))
    return "The sheet or range wasn't found. It may have been renamed or deleted.";
  if (/accessdenied|access denied|protected/i.test(msg))
    return "Excel blocked access — the sheet may be protected.";
  if (/invalidargument|invalid argument/i.test(msg))
    return "An operation used an invalid argument and was skipped.";
  if (/generalexception/i.test(msg))
    return "Excel ran into an internal issue. The operation was skipped.";
  if (/context.*invalidated|context is no longer valid/i.test(msg))
    return "The Excel context was reset — please try again.";
  if (/workbook.*not.*open|no workbook/i.test(msg))
    return "No workbook is open. Please open a workbook and try again.";
  if (/sheet.*already.*exist|duplicate.*sheet/i.test(msg))
    return "A sheet with that name already exists.";

  // ── Network / server errors ──
  if (/failed to fetch|network request failed|networkerror/i.test(msg))
    return "Couldn't reach the server. Check your connection and try again.";
  if (/401|unauthorized|unauthenticated/i.test(msg))
    return "Your session expired. Please sign in again.";
  if (/403|forbidden/i.test(msg))
    return "Access was denied for that request.";
  if (/429|rate limit|too many requests/i.test(msg))
    return "Too many requests — please wait a moment and try again.";
  if (/500|internal server error/i.test(msg))
    return "The server encountered an error. Please try again.";
  if (/503|service unavailable/i.test(msg))
    return "The server is temporarily unavailable. Please try again shortly.";
  if (/timeout|timed out/i.test(msg))
    return "The request timed out. Please try again.";

  // ── Agent / content errors ──
  if (/without generating/i.test(msg)) return ""; // intentionally suppressed upstream
  if (/json.*parse|unexpected token|syntaxerror/i.test(msg))
    return "The server returned an unexpected response. Please try again.";
  if (/context.*length|max.*token|token.*limit/i.test(msg))
    return "The request was too large. Try breaking it into smaller steps.";
  if (/api.*key|apikey|invalid.*key/i.test(msg))
    return "API authentication failed. Check your configuration.";

  // ── Fallback: strip technical prefixes and cap length ──
  const cleaned = msg
    .replace(/^Error:\s*/i, "")
    .replace(/^RichApi\.Error:\s*/i, "")
    .replace(/^OfficeExtension\.Error:\s*/i, "")
    .trim();
  return cleaned.length > 120 ? cleaned.slice(0, 120) + "…" : cleaned || "An unexpected error occurred.";
}
