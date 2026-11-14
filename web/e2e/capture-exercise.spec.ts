import { test } from '@playwright/test';
import path from 'path';
import { gotoPainted } from './helpers';

/*
 * Two viewport-sized views of the Exercise page, in dark mode:
 *   1. the top fold - the page as it lands (week strip, today's session, the dose)
 *   2. the bottom fold - scrolled to the end of the session list
 *
 * The animated SVG figure is driven by a requestAnimationFrame loop. Playwright's screenshot can catch it mid-update,
 * which leaves the figure area blank in the capture. Reduced motion freezes the loop at a static pose, so the
 * astronaut is drawn and the shot is stable.
 */

test.describe('Capture Exercise Screenshots', () => {
  test.use({ reducedMotion: 'reduce', colorScheme: 'dark' });

  test('capture exercise top and bottom folds in dark mode', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await gotoPainted(page, '/exercise');

    // Force the dark theme: the app stores it in localStorage and otherwise falls back to the OS preference.
    await page.evaluate(() => {
      document.documentElement.dataset.theme = 'dark';
      localStorage.setItem('astra-theme', 'dark');
    });
    await page.waitForTimeout(600);

    // Let the figure mount and paint its first frame.
    await page.waitForTimeout(1500);

    const outDir = path.resolve(process.cwd(), '../docs/screenshots');

    // 1. Top fold - the page as it first lands.
    await page.screenshot({
      path: path.join(outDir, 'exercise-fold.png'),
      fullPage: false,
    });

    // 2. Bottom fold - scrolled to the end of the page, still viewport-sized.
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await page.waitForTimeout(1200);
    await page.screenshot({
      path: path.join(outDir, 'exercise-bottom-fold.png'),
      fullPage: false,
    });
  });
});
