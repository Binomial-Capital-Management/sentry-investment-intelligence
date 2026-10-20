/**
 * Chrome tab constants — every value traced to Chromium source.
 * See chrome-source-reference/TRANSLATION.md for file:line citations.
 */

// --- Dimensions (non-touch desktop) ---

/** tab_style.cc:31 — constexpr int kTabWidth = 232 */
export const TAB_CONTENT_WIDTH = 232;

/** tab_style.cc:48 — kTabWidth + 2 * GetBottomCornerRadius() */
export const TAB_STANDARD_WIDTH = 180;

/** tab_style.cc:93 — return 10 */
export const TOP_CORNER_RADIUS = 10;

/** tab_style.cc:97 — return 12 */
export const BOTTOM_CORNER_RADIUS = 12;

/** layout_constants.cc:88 — 34 + kTabstripToolbarOverlap(1) */
export const TAB_HEIGHT = 35;

/** layout_constants.cc:103 — return 1 */
export const TOOLBAR_OVERLAP = 1;

/** layout_constants.cc:95 — return 6 */
export const TAB_STRIP_PADDING = 6;

/** layout_constants.cc:90 — kTabHeight + kTabStripPadding */
export const TAB_STRIP_HEIGHT = 41;

/**
 * tab_style_views.cc:236-245 — for fill path:
 * kTabHeight(35) - kTabStripPadding(6) - kTabstripToolbarOverlap(1) = 28
 */
export const TAB_BODY_HEIGHT = 28;

/** tab_style.cc:27 — constexpr int kChromeRefreshTabVerticalPadding = 6 */
export const TAB_VERTICAL_PADDING = 6;

/** tab_style.cc:28 — constexpr int kChromeRefreshTabHorizontalPadding = 8 */
export const TAB_HORIZONTAL_PADDING = 8;

/** layout_constants.cc:99 — return 8 */
export const TAB_PRE_TITLE_PADDING = 8;

/** layout_constants.cc:80 — return touch_ui ? 8 : 4 */
export const TAB_AFTER_TITLE_PADDING = 4;

/** layout_constants.cc:86 — return touch_ui ? 24 : 16 */
export const TAB_CLOSE_BUTTON_SIZE = 16;

/** tab_close_button.cc:45 — constexpr int kButtonPadding = 12 */
export const CLOSE_BUTTON_HIT_PADDING = 12;

/** favicon_size.h:13 — inline constexpr int kFaviconSize = 16 */
export const FAVICON_SIZE = 16;

/** tab.h:77 — static constexpr int kMinimumContentsWidthForCloseButtons = 68 */
export const CLOSE_MIN_CONTENT_WIDTH = 68;

/**
 * tab_style.cc:80-89 — kInteriorWidth(16) - SeparatorSize.width(2) + GetTabOverlap(18) = 32
 */
export const TAB_MIN_INACTIVE_WIDTH = 32;

/** tab_style.cc:53 — constexpr int kTabPinnedContentWidth = 24 */
export const TAB_PINNED_CONTENT_WIDTH = 24;

/**
 * tab_style.cc:273-281 — GetContentsInsets()
 * left/right = GetBottomCornerRadius(12) + kChromeRefreshTabHorizontalPadding(8) = 20
 */
export const CONTENTS_INSET_HORIZONTAL = 20;

// --- Separator ---

/** tab_style.cc:21 */
export const SEPARATOR_THICKNESS = 2;

/** tab_style.cc:24 */
export const SEPARATOR_HEIGHT = 16;

/** tab_style.cc:22 */
export const SEPARATOR_HORIZONTAL_MARGIN = 2;

/** tab_style.cc:126 — GetSeparatorSize().width() / 2 */
export const SEPARATOR_CORNER_RADIUS = 1;

/** tab_style.cc:104 — 2 * GetBottomCornerRadius(12) - (2*2 + 2) = 18 */
export const TAB_OVERLAP = 18;

// --- Animation ---

/** tab_container_impl.cc:1117 — base::Milliseconds(200) */
export const BOUNDS_ANIMATION_MS = 200;

/** glow_hover_controller.cc:40 — base::Milliseconds(200) */
export const GLOW_SHOW_MS = 200;

/** glow_hover_controller.cc:41 — gfx::Tween::EASE_OUT */
export const GLOW_SHOW_EASING = 'ease-out';

/** glow_hover_controller.cc:56 — gfx::Tween::EASE_IN */
export const GLOW_HIDE_EASING = 'ease-in';

/** glow_hover_controller.cc:13 — static const double kSubtleOpacityScale = 0.45 */
export const GLOW_SUBTLE_OPACITY = 0.45;

// --- Colors (baseline neutral, light mode, frame active) ---
// All traced through material_tab_strip_color_mixer.cc → sys_color_mixer.cc → ref_color_mixer.cc

export const colors = {
  /** kColorTabBackgroundActiveFrameActive → kColorSysBase → kColorRefNeutral100 → ref_color_mixer.cc:114 */
  activeBg: '#FFFFFF',

  /** kColorTabBackgroundInactiveFrameActive → kColorSysHeader → kColorRefNeutral90 → ref_color_mixer.cc:107 */
  inactiveBg: '#E3E3E3',

  /** kColorTabBackgroundInactiveHoverFrameActive → kColorSysStateHeaderHover → kColorRefNeutral80 → ref_color_mixer.cc:105 */
  hoverBg: '#C7C7C7',

  /** kColorTabForegroundActiveFrameActive → kColorSysOnSurface → kColorRefNeutral10 → ref_color_mixer.cc:92 */
  activeText: '#1F1F1F',

  /** kColorTabForegroundInactiveFrameActive → BlendForMinContrast(kColorRefNeutral30) → ref_color_mixer.cc:100 */
  inactiveText: '#474747',

  /** kColorTabDividerFrameActive → kColorSysOnHeaderDivider → kColorRefNeutral80 → ref_color_mixer.cc:105 */
  divider: '#C7C7C7',

  /** Strip background = same as inactive tab bg (frame color) */
  stripBg: '#E3E3E3',
} as const;

// --- Hover contrast values (from tab_style.cc:151-164) ---

/** tab_style.cc:153 — hover opacity ~0.4 for standard-width tabs */
export const HOVER_OPACITY_STANDARD = 0.4;

/** tab_style.cc:158 — hover opacity ~0.65 for min-width tabs */
export const HOVER_OPACITY_NARROW = 0.65;

/** tab_style.cc:163 — radial gradient highlight opacity ~0.45 */
export const HOVER_OPACITY_RADIAL = 0.45;

// --- Z-ordering (from tab_style_views.cc:620-643) ---

export const Z_INACTIVE = 0;
export const Z_HOVER = 2;
export const Z_SELECTED = 4;
export const Z_ACTIVE = 6;
