/**
 * Mouse-tracking radial glow hover effect.
 *
 * Source: glow_hover_controller.cc
 *   Line 10-13: Radial gradient #FFF 0.9 center → #FFF 0.0 edge, gradient opacity 0.5
 *               Premultiplied: 0.9 * 0.5 = 0.45 (kSubtleOpacityScale)
 *   Line 40: Show duration = 200ms
 *   Line 41: Show tween = EASE_OUT
 *   Line 56: Hide tween = EASE_IN
 *   Line 73-74: Alpha = CurrentValueBetween(0, round(255 * opacity_scale))
 *
 * Drives CSS custom properties --glow-x, --glow-y, --glow-opacity
 * which are consumed by .chrome-tab-glow radial-gradient in chromeTab.css.
 */

import { useRef, useCallback, type MouseEvent as ReactMouseEvent } from 'react';
import { GLOW_SUBTLE_OPACITY, GLOW_SHOW_MS } from './chromeTabConstants';

export function useGlowHover() {
  const rafId = useRef(0);

  const initRef = useCallback((node: HTMLDivElement | null) => {
    if (node) {
      node.style.setProperty('--glow-x', '50%');
      node.style.setProperty('--glow-y', '50%');
      node.style.setProperty('--glow-opacity', '0');
    }
  }, []);

  /** glow_hover_controller.cc — SetLocation equivalent */
  const onMouseMove = useCallback((e: ReactMouseEvent) => {
    const el = e.currentTarget as HTMLDivElement;
    const { clientX, clientY } = e;
    cancelAnimationFrame(rafId.current);
    rafId.current = requestAnimationFrame(() => {
      const rect = el.getBoundingClientRect();
      el.style.setProperty('--glow-x', `${clientX - rect.left}px`);
      el.style.setProperty('--glow-y', `${clientY - rect.top}px`);
    });
  }, []);

  /** glow_hover_controller.cc:36-43 — Show(kSubtle): 200ms EASE_OUT to 0.45 opacity */
  const onMouseEnter = useCallback((e: ReactMouseEvent) => {
    const el = e.currentTarget as HTMLDivElement;
    const glow = el.querySelector<HTMLElement>('.chrome-tab-glow');
    if (glow) {
      glow.style.transition = `opacity ${GLOW_SHOW_MS}ms ease-out`;
      glow.style.opacity = '1';
    }
    el.style.setProperty('--glow-opacity', String(GLOW_SUBTLE_OPACITY));
  }, []);

  /** glow_hover_controller.cc:53-58 — Hide(kGradual): EASE_IN fade out */
  const onMouseLeave = useCallback((e: ReactMouseEvent) => {
    const el = e.currentTarget as HTMLDivElement;
    const glow = el.querySelector<HTMLElement>('.chrome-tab-glow');
    if (glow) {
      glow.style.transition = `opacity ${GLOW_SHOW_MS}ms ease-in`;
      glow.style.opacity = '0';
    }
    el.style.setProperty('--glow-opacity', '0');
  }, []);

  return { ref: initRef, onMouseMove, onMouseEnter, onMouseLeave };
}
