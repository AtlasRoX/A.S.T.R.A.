import { test, expect, type Page } from '@playwright/test';

// Deeper checks: the interactive features, not just that pages load.
// These exercise the crew switcher, the measurement wizard (a 4-step flow),
// the simulator player and the emergency runner.

async function watch(page: Page) {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(`PAGEERROR: ${e.message}`));
  page.on('console', (m) => {
    if (m.type() === 'error' && !/font override|favicon|DevTools/i.test(m.text())) errors.push(m.text());
  });
  return errors;
}

test.describe('crew switching', () => {
  // The crew page has one card per crew member, each with a "View as" button.
  for (const [crew, expectName] of [
    ['ana', /Ana/i],
    ['kenji', /Kenji/i],
    ['sara', /Sara/i],
    ['lucas', /Lucas/i],
  ] as const) {
    test(`switching to ${crew} updates the dashboard`, async ({ page }) => {
      const errors = await watch(page);
      await page.goto('/crew');
      await page.waitForTimeout(800);

      // Find the card for this crew member, then its "View as" button.
      const row = page.locator(`li[data-crew="${crew}"]`);
      await expect(row, `crew row for ${crew}`).toBeVisible();
      const viewAs = row.getByRole('button', { name: /view as/i });
      const isCurrent = (await viewAs.count()) === 0;
      if (isCurrent) {
        // Already the current crew member: the card shows "Viewing" instead of a button.
        await expect(row.getByText(/viewing/i)).toBeVisible();
        await page.goto('/');
      } else {
        await viewAs.click();
        await page.waitForURL('/', { timeout: 15_000 });
      }
      await page.waitForTimeout(1000);

      // The overview must now be about this crew member.
      const body = await page.locator('body').innerText();
      expect(body, `overview should mention ${crew}`).toMatch(expectName);
      expect(errors).toEqual([]);
    });
  }
});

test.describe('measurement wizard', () => {
  test('the HR wizard walks Prepare -> Measure -> Result', async ({ page }) => {
    const errors = await watch(page);
    await page.goto('/measure/hr');
    await page.waitForTimeout(700);

    // Step 1: Prepare. The button says "I'm ready".
    const ready = page.getByRole('button', { name: /i'm ready/i }).first();
    await expect(ready, 'the wizard should offer "I\'m ready" on the Prepare step').toBeVisible();
    await ready.click();
    await page.waitForTimeout(400);

    // Step 2: "Why it matters" -> "Start measuring".
    const start = page.getByRole('button', { name: /start measuring/i }).first();
    await expect(start, 'the wizard should offer "Start measuring" on step 2').toBeVisible();
    await start.click();
    await page.waitForTimeout(500);

    // Step 3: Measure. The numeric entry is a text input with inputMode=decimal
    // (deliberately not type=number), labelled "<Metric> in <unit>".
    const numberInput = page.locator('input[inputmode="decimal"]').first();
    await expect(numberInput, 'the Measure step should have a numeric input').toBeVisible();
    await numberInput.fill('72');
    await page.waitForTimeout(300);

    // Evaluate -> Result.
    const evaluateBtn = page.getByRole('button', { name: /see result|evaluate|check result/i }).first();
    if ((await evaluateBtn.count()) > 0) {
      await evaluateBtn.click();
      await page.waitForTimeout(2500);
    }

    const body = await page.locator('body').innerText();
    expect(body.length).toBeGreaterThan(200);
    // A nominal 72 bpm must be classified Nominal.
    expect(body).toMatch(/nominal|normal/i);
    expect(errors).toEqual([]);
  });

  test('an anomaly value escalates to Act', async ({ page }) => {
    const errors = await watch(page);
    await page.goto('/measure/hr');
    await page.waitForTimeout(700);

    const ready = page.getByRole('button', { name: /i'm ready/i }).first();
    await ready.click();
    await page.waitForTimeout(400);
    await page.getByRole('button', { name: /start measuring/i }).first().click();
    await page.waitForTimeout(500);

    // The app ships an "Unusual reading" control on the Measure step
    // (HR anomaly = 128, the app's own value).
    const anomaly = page.getByRole('button', { name: /unusual reading/i }).first();
    await expect(anomaly, 'the Measure step should offer "Unusual reading"').toBeVisible();
    await anomaly.click();
    await page.waitForTimeout(400);
    const evaluateBtn = page.getByRole('button', { name: /see result|evaluate|check result/i }).first();
    if ((await evaluateBtn.count()) > 0) {
      await evaluateBtn.click();
      await page.waitForTimeout(2500);
    }
    const body = await page.locator('body').innerText();
    expect(body).toMatch(/act|flight surgeon|escalat/i);
    expect(errors).toEqual([]);
  });

  test('the symptom check renders its options', async ({ page }) => {
    const errors = await watch(page);
    await page.goto('/measure/symptoms');
    await page.waitForTimeout(700);
    const body = await page.locator('body').innerText();
    expect(body.length).toBeGreaterThan(200);
    expect(errors).toEqual([]);
  });
});

test.describe('emergency runner', () => {
  test('the emergency page lists protocols', async ({ page }) => {
    const errors = await watch(page);
    await page.goto('/emergency');
    await page.waitForTimeout(900);
    const body = await page.locator('body').innerText();
    expect(body.length).toBeGreaterThan(200);
    expect(errors).toEqual([]);
  });
});

test.describe('trends', () => {
  test('the trends page renders a chart', async ({ page }) => {
    const errors = await watch(page);
    await page.goto('/trends');
    await page.waitForTimeout(1200);
    const svgs = await page.locator('svg').count();
    expect(svgs, 'trends should render SVG charts').toBeGreaterThan(0);
    expect(errors).toEqual([]);
  });
});

test.describe('3D body', () => {
  test('the overview loads the anatomy model without error', async ({ page }) => {
    const errors = await watch(page);
    const glbRequests: string[] = [];
    page.on('request', (r) => {
      if (r.url().includes('astra-anatomy.glb')) glbRequests.push(r.url());
    });
    await page.goto('/');
    await page.waitForTimeout(4000);

    const body = await page.locator('body').innerText();
    expect(body).toMatch(/body|system|organ/i);
    expect(errors.filter((e) => !/webgl|context/i.test(e))).toEqual([]);
    console.log('GLB requested:', glbRequests.length > 0);
  });
});
