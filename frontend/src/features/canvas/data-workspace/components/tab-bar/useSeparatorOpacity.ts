/**
 * Tab separator opacity computation.
 *
 * Source: tab_style_views.cc
 *   Line 727-836: GetSeparatorOpacity + GetHoverInterpolatedSeparatorOpacity
 *   Line 753: opacity = 0 if tab has_visible_background (active, selected, hovered)
 *   Line 793: opacity = 0 if adjacent tab has_visible_background
 *   Line 828-835: GetHoverInterpolatedSeparatorOpacity:
 *     return 1.0 - max(hover_value, adjacent_hover_value)
 */

import { useMemo } from 'react';

interface TabState {
  isActive: boolean;
  isHovered: boolean;
}

/**
 * Returns separator opacities (length = tabs.length - 1).
 * Each value is for the gap between tabs[i] and tabs[i+1].
 */
export function useSeparatorOpacity(tabs: TabState[]): number[] {
  return useMemo(() => {
    if (tabs.length <= 1) return [];

    const opacities: number[] = [];
    for (let i = 0; i < tabs.length - 1; i++) {
      const left = tabs[i];
      const right = tabs[i + 1];

      // tab_style_views.cc:753 — no separator if either neighbor has visible background
      if (left.isActive || left.isHovered || right.isActive || right.isHovered) {
        opacities.push(0);
      } else {
        // tab_style_views.cc:835 — full opacity between two plain inactive tabs
        opacities.push(1);
      }
    }
    return opacities;
  }, [tabs]);
}
