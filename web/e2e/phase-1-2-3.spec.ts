import { test, expect } from '@playwright/test';
import { gotoPainted } from './helpers';

/**
 * The roadmap's remaining Phase 1-3 items: background simulation (no demo pages), reading source and stale labels,
 * 44px targets, Reference tabs, Routine now-line, quick entry, radio-group keyboard, offline protocols.
 */

test.describe('Simulation runs behind the scenes', () => {
  // ASTRA Core starts the background telemetry itself; there is no demo or simulator page to open.
  test('/demo and /simulate no longer exist, and nothing links to them', async ({ page, request }) => {
    for (const path of ['/demo', '/simulate']) {
      const res = await request.get(path);
      expect(res.status(), path).toBe(404);
    }
    await page.setViewportSize({ width: 1440, height: 900 });
    for (const path of ['/', '/settings']) {
      await gotoPainted(page, path);
      await expect(page.locator('a[href="/demo"], a[href^="/simulate"]')).toHaveCount(0);
    }
  });
});

test.describe('Reading source and stale state', () => {
  test('the Overview vitals show where each reading came from', async ({ page }) => {
    await gotoPainted(page, '/');
    const sources = page.locator('[data-source]');
    await expect(sources.first()).toBeAttached();
    expect(await sources.count()).toBeGreaterThan(3);
  });

  test('Measure lists due checks, then checks that need a re-look, then all checks', async ({ page }) => {
    await gotoPainted(page, '/measure');
    await expect(page.getByRole('heading', { name: 'All checks' })).toBeVisible();
    const order = await page.locator('h2').allInnerTexts();
    const allIdx = order.findIndex((t) => /All checks/.test(t));
    const dueIdx = order.findIndex((t) => /Due now/.test(t));
    const reIdx = order.findIndex((t) => /Needs re-check/.test(t));
    if (dueIdx !== -1) expect(dueIdx).toBeLessThan(allIdx);
    if (reIdx !== -1) expect(reIdx).toBeLessThan(allIdx);
  });
});

test.describe('Reference area', () => {
  test('Guide, NASA data and Real astronauts share one set of tabs', async ({ page }) => {
    for (const path of ['/learn', '/data', '/data/inspiration4']) {
      await gotoPainted(page, path);
      const tabs = page.getByRole('navigation', { name: 'Reference sections' });
      await expect(tabs.getByRole('link', { name: 'Guide' })).toBeVisible();
      await expect(tabs.getByRole('link', { name: 'NASA data' })).toBeVisible();
      await expect(tabs.getByRole('link', { name: 'Real astronauts' })).toBeVisible();
    }
  });

  test('an evidence link opens its collapsed document group and lands on the card', async ({ page }) => {
    await gotoPainted(page, '/data');
    const groups = page.locator('details');
    expect(await groups.count()).toBeGreaterThan(1);
    // pick a document inside a group that starts closed
    const closed = page.locator('details:not([open]) article[id^="doc-"]').first();
    const id = await closed.getAttribute('id');
    expect(id).toBeTruthy();
    await page.goto(`/data#${id}`, { waitUntil: 'domcontentloaded' });
    await expect(page.locator(`#${id}`)).toBeVisible({ timeout: 15_000 });
  });
});

test.describe('Routine', () => {
  test('shows a Next up card and a now line', async ({ page }) => {
    await gotoPainted(page, '/routine');
    await expect(page.getByText(/Next up|Due now|Overdue/).first()).toBeVisible();
    await expect(page.getByLabel(/^Now, \d\d:\d\d$/)).toBeVisible();
  });
});

test.describe('Measure wizard', () => {
  test('Quick entry skips straight to the reading', async ({ page }) => {
    await gotoPainted(page, '/measure/hr');
    await page.getByRole('button', { name: 'Quick entry' }).click();
    await expect(page.getByRole('heading', { name: 'Enter your reading' })).toBeVisible();
  });

  test('the measurement-context radio group works with arrow keys', async ({ page }) => {
    await gotoPainted(page, '/measure/hr');
    await page.getByRole('button', { name: 'Quick entry' }).click();
    const group = page.getByRole('radiogroup', { name: 'Measurement context' });
    const radios = group.getByRole('radio');
    await radios.first().focus();
    await page.keyboard.press('ArrowRight');
    await expect(radios.nth(1)).toHaveAttribute('aria-checked', 'true');
    await page.keyboard.press('End');
    await expect(radios.last()).toHaveAttribute('aria-checked', 'true');
  });
});

test.describe('Touch targets on a phone', () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true });

  test('buttons and tabs on the main pages are at least 44px tall', async ({ page }) => {
    for (const path of ['/', '/measure', '/trends', '/crew', '/routine']) {
      await gotoPainted(page, path);
      const small = await page.evaluate(() => {
        const out: string[] = [];
        document.querySelectorAll<HTMLElement>('button, .btn, [role=tab], [role=radio], select, summary').forEach((e) => {
          const r = e.getBoundingClientRect();
          const cs = getComputedStyle(e);
          if (!r.width || !r.height || cs.visibility === 'hidden') return;
          if (r.height < 43.5) out.push(`${e.tagName}.${String(e.className).slice(0, 30)} ${Math.round(r.width)}x${Math.round(r.height)} "${(e.innerText || e.getAttribute('aria-label') || '').slice(0, 20)}"`);
        });
        return out;
      });
      expect(small, `${path}: ${small.join('; ')}`).toEqual([]);
    }
  });
});

test.describe('Offline protocols', () => {
  test('the static protocol copy is served and complete', async ({ request }) => {
    const res = await request.get('/emergency-protocols.json');
    expect(res.ok()).toBeTruthy();
    const protocols = (await res.json()) as { id: string; name: string; tracks: unknown[] }[];
    expect(protocols.length).toBe(4);
    for (const p of protocols) {
      expect(p.name).toBeTruthy();
      expect(p.tracks.length).toBeGreaterThan(0);
    }
  });
});
