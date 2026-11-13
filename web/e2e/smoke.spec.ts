import { test, expect, type Page } from '@playwright/test';

// Every page ASTRA ships. Each must render real content, with no console errors
// and no failed network requests.
const ROUTES = [
  { path: '/', name: 'Overview' },
  { path: '/measure', name: 'Measure' },
  { path: '/measure/hr', name: 'Measure HR' },
  { path: '/measure/bp', name: 'Measure BP' },
  { path: '/measure/spo2', name: 'Measure SpO2' },
  { path: '/measure/resp', name: 'Measure RR' },
  { path: '/measure/temp', name: 'Measure Temp' },
  { path: '/measure/glucose', name: 'Measure Glucose' },
  { path: '/measure/hydration', name: 'Measure Hydration' },
  { path: '/measure/mass', name: 'Measure Mass' },
  { path: '/measure/nutrition', name: 'Measure Nutrition' },
  { path: '/measure/sleep', name: 'Measure Sleep' },
  { path: '/measure/mood', name: 'Measure Mood' },
  { path: '/measure/reaction', name: 'Measure Reaction' },
  { path: '/measure/exercise', name: 'Measure Exercise' },
  { path: '/measure/vision', name: 'Measure Vision' },
  { path: '/measure/symptoms', name: 'Measure Symptoms' },
  { path: '/trends', name: 'Trends' },
  { path: '/routine', name: 'Routine' },
  { path: '/crew', name: 'Crew & comms' },
  { path: '/emergency', name: 'Emergency' },
  { path: '/learn', name: 'Health library' },
  { path: '/data', name: 'Data' },
  { path: '/data/inspiration4', name: 'Inspiration4' },
  { path: '/settings', name: 'Settings' },
];

// Console errors that are noise rather than defects.
const IGNORED_CONSOLE = [
  /Failed to load resource.*favicon/i,
  /Download the React DevTools/i,
  /font override values/i,
  /Warning: Each child in a list/i, // React key warnings - real but non-fatal; reported separately
];

function track(page: Page) {
  const consoleErrors: string[] = [];
  const failedRequests: string[] = [];
  const httpErrors: string[] = [];

  page.on('console', (msg) => {
    if (msg.type() !== 'error') return;
    const text = msg.text();
    if (IGNORED_CONSOLE.some((re) => re.test(text))) return;
    consoleErrors.push(text);
  });
  page.on('pageerror', (err) => consoleErrors.push(`PAGEERROR: ${err.message}`));
  page.on('requestfailed', (req) => {
    failedRequests.push(`${req.method()} ${req.url()} :: ${req.failure()?.errorText}`);
  });
  page.on('response', (res) => {
    if (res.status() >= 400) httpErrors.push(`${res.status()} ${res.url()}`);
  });

  return { consoleErrors, failedRequests, httpErrors };
}

for (const route of ROUTES) {
  test(`route ${route.path} renders cleanly`, async ({ page }) => {
    const t = track(page);
    const res = await page.goto(route.path, { waitUntil: 'domcontentloaded', timeout: 45_000 });

    expect(res?.status(), `${route.path} HTTP status`).toBeLessThan(400);

    // Wait for the page to actually paint its main content. The dev server can
    // recompile a route on first hit, and the 3D body keeps the network busy,
    // so neither `networkidle` nor an immediate read is reliable here.
    await page.waitForFunction(
      () => (document.body.innerText ?? '').trim().length > 120,
      undefined,
      { timeout: 30_000 },
    );
    await expect(page.locator('body')).toBeVisible();

    // No Next.js error boundary / not-found.
    const bodyText = (await page.locator('body').innerText()).toLowerCase();
    expect(bodyText, `${route.path} shows an error page`).not.toContain('application error');
    expect(bodyText, `${route.path} shows 404`).not.toContain('this page could not be found');
    expect(bodyText, `${route.path} shows engine offline`).not.toContain('astra core is offline');

    // Real content, not an empty shell.
    const textLength = bodyText.trim().length;
    expect(textLength, `${route.path} rendered almost no text (${textLength} chars)`).toBeGreaterThan(120);

    expect(t.httpErrors, `${route.path} HTTP errors: ${t.httpErrors.join(' | ')}`).toEqual([]);
    expect(t.failedRequests, `${route.path} failed requests: ${t.failedRequests.join(' | ')}`).toEqual([]);
    expect(t.consoleErrors, `${route.path} console errors: ${t.consoleErrors.join(' | ')}`).toEqual([]);
  });
}
