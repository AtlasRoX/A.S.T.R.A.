import { expect, type Page } from '@playwright/test';

/**
 * Navigate and wait for the page to actually paint.
 *
 * `networkidle` is unusable on pages with the 3D body: the WebGL render loop
 * keeps the connection open, so the network never goes idle and the wait
 * times out. Wait for real text content instead.
 */
export async function gotoPainted(page: Page, path: string, minChars = 120): Promise<void> {
  await page.goto(path, { waitUntil: 'domcontentloaded', timeout: 45_000 });
  await page.waitForFunction(
    (min) => (document.body.innerText ?? '').trim().length > min,
    minChars,
    { timeout: 30_000 },
  );
  await expect(page.locator('body')).toBeVisible();
}
