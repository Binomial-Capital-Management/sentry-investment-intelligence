import { ThinkingSection } from "../../shared/types";

/**
 * Cache for incremental parsing - avoids re-parsing entire text on each token.
 */
export interface ParseCache {
  lastText: string;
  sections: ThinkingSection[];
  sectionIdBase: number;
}

export const parseCache: ParseCache = { lastText: "", sections: [], sectionIdBase: 0 };

/**
 * Reset the parse cache (call when starting a new agent run).
 */
export function resetParseCache(): void {
  parseCache.lastText = "";
  parseCache.sections = [];
  parseCache.sectionIdBase = Date.now();
}

/**
 * Full parse of thinking text into sections.
 * Used as fallback when incremental parsing isn't possible.
 */
export function fullParseThinkingSections(text: string, idBase: number): ThinkingSection[] {
  const sections: ThinkingSection[] = [];
  
  const boldPattern = /\*\*([^*]+)\*\*/g;
  const matches: Array<{ title: string; startIdx: number; endIdx: number }> = [];
  
  let match;
  while ((match = boldPattern.exec(text)) !== null) {
    matches.push({
      title: match[1].trim(),
      startIdx: match.index,
      endIdx: match.index + match[0].length,
    });
  }
  
  for (let i = 0; i < matches.length; i++) {
    const current = matches[i];
    const nextStart = i < matches.length - 1 ? matches[i + 1].startIdx : text.length;
    const content = text.slice(current.endIdx, nextStart).trim();
    
    sections.push({
      id: `thinking-${i}-${idBase}`,
      title: current.title,
      content,
      collapsed: false,
    });
  }
  
  if (sections.length === 0 && text.trim()) {
    const firstPeriod = text.indexOf(".");
    if (firstPeriod >= 15 && firstPeriod < 100) {
      const title = text.slice(0, firstPeriod + 1).trim();
      const content = text.slice(firstPeriod + 1).trim();
      sections.push({
        id: `thinking-0-${idBase}`,
        title,
        content,
        collapsed: false,
      });
    } else {
      const title = text.slice(0, 60).trim() + (text.length > 60 ? "..." : "");
      sections.push({
        id: `thinking-0-${idBase}`,
        title,
        content: text,
        collapsed: false,
      });
    }
  }
  
  return sections;
}

/**
 * Parse thinking text into sections with titles and content.
 * Uses incremental caching - if text is just appended, only update the last section's content.
 */
export function parseThinkingSections(text: string): ThinkingSection[] {
  if (!text.trim()) {
    return [];
  }
  
  // Check if we can use incremental update (text is appended to previous)
  if (
    text.startsWith(parseCache.lastText) &&
    parseCache.sections.length > 0 &&
    parseCache.lastText.length > 0
  ) {
    const delta = text.slice(parseCache.lastText.length);
    
    // If delta doesn't contain new section markers, just update last section's content
    if (!delta.includes("**")) {
      const sections = parseCache.sections.map((s, idx) => {
        if (idx === parseCache.sections.length - 1) {
          return { ...s, content: s.content + delta };
        }
        return s;
      });
      parseCache.lastText = text;
      parseCache.sections = sections;
      return sections;
    }
  }
  
  // Full parse (fallback)
  const sections = fullParseThinkingSections(text, parseCache.sectionIdBase);
  parseCache.lastText = text;
  parseCache.sections = sections;
  return sections;
}
