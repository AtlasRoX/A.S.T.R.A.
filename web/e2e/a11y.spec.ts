import { test, expect } from '@playwright/test';
import { gotoPainted } from './helpers';

// Accessibility and responsiveness checks on the pages the brief calls out:
// a colour-coded status that must always have a text label, and a clickable human figure.
const PAGES = ['/', '/trends', '/measure/hr', '/routine', '/crew', '/emergency'];

// Pages that display a classified status. /measure/hr and /routine are pre-measurement
// (a pending task or an unmeasured metric has no status yet) and /emergency lists
// protocols rather than classified results, so they legitimately show no status word.
const STATUS_PAGES = new Set(['/', '/trends', '/crew']);

test.describe('accessibility', () => {
  for (const path of PAGES) {
    test(`${path} has no obvious a11y violations`, async ({ page }) => {
      // Not `networkidle`: the 3D body on `/` keeps a render loop alive, so the
      // network never goes idle. Wait for the DOM instead.
      await gotoPainted(page, path);
      await page.waitForTimeout(800);

      // Every image/svg with a role=img needs an accessible name.
      const unnamedImgs = await page.locator('svg[role="img"]').evaluateAll((els) =>
        els.filter((e) => !e.getAttribute('aria-label') && !e.querySelector('title')).length,
      );
      expect(unnamedImgs, `${path} has svg[role=img] without a label`).toBe(0);

      // Buttons must have an accessible name (text, aria-label or title).
      const unnamedButtons = await page.locator('button').evaluateAll((els) =>
        els.filter((b) => {
          const text = (b.textContent || '').trim();
          const label = b.getAttribute('aria-label') || b.getAttribute('title');
          return text.length === 0 && !label;
        }).length,
      );
      expect(unnamedButtons, `${path} has buttons without an accessible name`).toBe(0);

      // Status must be conveyed by text, not colour alone (the brief asks for
      // colour coding that helps "at a glance", but the house rule is a text label too).
      // The label may be nested inside a wrapper, so match on text content, not exact element text.
      if (STATUS_PAGES.has(path)) {
        const bodyText = await page.locator('body').innerText();
        const hasStatusWord = /\b(Nominal|Watch|Act)\b/.test(bodyText);
        expect(hasStatusWord, `${path} should show a textual status label`).toBe(true);
      }
    });
  }
});

test.describe('responsiveness', () => {
  for (const [w, h, label] of [
    [390, 844, 'iPhone 12'],
    [768, 1024, 'iPad'],
  ] as const) {
    test(`${label} layout has no horizontal overflow`, async ({ page }) => {
      await page.setViewportSize({ width: w, height: h });
      await gotoPainted(page, '/');
      await page.waitForTimeout(1000);

      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      expect(overflow, `${label} should not scroll horizontally (overflow ${overflow}px)`).toBeLessThanOrEqual(2);
    });
  }
});
