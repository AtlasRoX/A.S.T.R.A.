import { test } from '@playwright/test';
import path from 'path';
import { gotoPainted } from './helpers';

const VIEWPORTS = [
  { width: 1440, height: 900, name: '1440' },
  { width: 1024, height: 768, name: '1024' },
  { width: 768, height: 1024, name: '768' },
  { width: 390, height: 844, name: '390' },
];

const THEMES = ['dark', 'light'] as const;

test.describe('Capture Today & Shell Screenshots', () => {
  for (const theme of THEMES) {
    for (const vp of VIEWPORTS) {
      test(`capture today and shell at ${vp.width}x${vp.height} in ${theme} mode`, async ({ page }) => {
        await page.setViewportSize({ width: vp.width, height: vp.height });
        await gotoPainted(page, '/');

        // Set theme
        await page.evaluate((th) => {
          document.documentElement.dataset.theme = th;
          localStorage.setItem('astra-theme', th);
        }, theme);
        await page.waitForTimeout(600);

        const outDir = path.resolve(process.cwd(), '../docs/ux/screens');

        // Today full page screenshot
        await page.screenshot({
          path: path.join(outDir, `today-${vp.name}-${theme}.png`),
          fullPage: true,
        });

        // Shell viewport fold screenshot
        await page.screenshot({
          path: path.join(outDir, `shell-${vp.name}-${theme}.png`),
          fullPage: false,
        });
      });
    }
  }
});
