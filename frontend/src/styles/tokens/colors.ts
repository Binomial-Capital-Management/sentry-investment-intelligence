export type ThemeMode = 'dark' | 'light';

// Palantir AIP-inspired light theme with clean, professional colors
export const Colors = {
  // Background colors - clean whites and subtle grays
  bg: {
    void: '#FFFFFF',        // Pure white for main background
    base: '#FAFBFC',        // Very light gray for base surfaces
    surface: '#F7F9FB',     // Light gray for cards and panels
    subtle: '#F0F2F5',      // Subtle gray for hover states
    overlay: '#FFFFFF',     // White for overlays with shadow
  },
  // Text colors - high contrast for readability
  text: {
    primary: '#0F172A',     // Dark slate for primary text
    secondary: '#475569',   // Medium slate for secondary text
    muted: '#94A3B8',       // Light slate for muted text
  },
  // Intent colors - professional and accessible
  intent: {
    accent: '#3B82F6',      // Professional blue (primary brand)
    success: '#10B981',     // Emerald green for success
    warning: '#F59E0B',     // Amber for warnings
    danger: '#EF4444',      // Red for errors/danger
  },
  // Border colors - subtle and clean
  border: {
    subtle: '#F1F5F9',      // Very light border
    default: '#E2E8F0',     // Default border color
    strong: '#CBD5E1',      // Stronger border for emphasis
  },
  // Chart colors - vibrant but professional palette
  chart: [
    '#3B82F6',  // Blue
    '#10B981',  // Emerald
    '#8B5CF6',  // Violet
    '#F59E0B',  // Amber
    '#EC4899',  // Pink
    '#14B8A6',  // Teal
    '#F97316',  // Orange
  ],
} as const;

export function alpha(hex: string, a: number): string {
  const clamp = (v: number, min = 0, max = 1) => Math.max(min, Math.min(max, v));
  const c = hex.replace('#', '');
  const bigint = parseInt(c.length === 3 ? c.split('').map((x) => x + x).join('') : c, 16);
  const r = (bigint >> 16) & 255;
  const g = (bigint >> 8) & 255;
  const b = bigint & 255;
  const aa = Math.round(clamp(a) * 255);
  return `rgba(${r}, ${g}, ${b}, ${aa / 255})`;
}

export function mix(hex1: string, hex2: string, ratio = 0.5): string {
  const clamp = (v: number, min = 0, max = 1) => Math.max(min, Math.min(max, v));
  const r = clamp(ratio);
  const parse = (hex: string) => {
    const c = hex.replace('#', '');
    const v = parseInt(c.length === 3 ? c.split('').map((x) => x + x).join('') : c, 16);
    return [(v >> 16) & 255, (v >> 8) & 255, v & 255];
  };
  const [r1, g1, b1] = parse(hex1);
  const [r2, g2, b2] = parse(hex2);
  const rr = Math.round(r1 * (1 - r) + r2 * r);
  const gg = Math.round(g1 * (1 - r) + g2 * r);
  const bb = Math.round(b1 * (1 - r) + b2 * r);
  return `rgb(${rr}, ${gg}, ${bb})`;
}
