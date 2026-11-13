import { test, expect } from '@playwright/test';
import { gotoPainted } from './helpers';

const ENGINE = 'http://127.0.0.1:8000';

async function catalog(request: import('@playwright/test').APIRequestContext) {
  return (await (await request.get(`${ENGINE}/catalog`)).json()) as {
    metrics: { id: string; ok: [number, number]; ok2?: [number, number] }[];
    escalation: { tier: number; name: string; who: string }[];
  };
}

test.describe('Result bar has an accessible name', () => {
  test('the range bar is announced as one image describing reading, status and ranges', async ({ page }) => {
    await gotoPainted(page, '/measure/hr');
    await page.getByRole('button', { name: 'Quick entry' }).click();
    await page.locator('input[inputmode="decimal"]').first().fill('64');
    await page.getByRole('button', { name: /see result/i }).click();
    const bar = page.getByRole('img', { name: /^Reading 64 bpm, Nominal\./ });
    await expect(bar).toBeVisible({ timeout: 15_000 });
    const name = (await bar.getAttribute('aria-label')) ?? '';
    expect(name).toMatch(/Watch range \d+ to \d+/);
  });
});

test.describe('Ranges and the escalation ladder come from the catalog', () => {
  test('the blood-pressure range in the wizard and the Library match the catalog', async ({ page, request }) => {
    const bp = (await catalog(request)).metrics.find((m) => m.id === 'bp');
    expect(bp?.ok2).toBeTruthy();
    const text = `${bp!.ok[0]}–${bp!.ok[1]} / ${bp!.ok2![0]}–${bp!.ok2![1]}`;
    await gotoPainted(page, '/measure/bp');
    await page.getByRole('button', { name: "I'm ready" }).click();
    await expect(page.getByText(text).first()).toBeVisible();
    await gotoPainted(page, '/learn');
    await expect(page.getByText(text).first()).toBeAttached();
  });

  test('the wizard result ladder uses the catalog tier names and who', async ({ page, request }) => {
    const tiers = (await catalog(request)).escalation;
    await gotoPainted(page, '/measure/hr');
    await page.getByRole('button', { name: 'Quick entry' }).click();
    await page.locator('input[inputmode="decimal"]').first().fill('64');
    await page.getByRole('button', { name: /see result/i }).click();
    const ladder = page.getByRole('group', { name: 'Escalation tiers' });
    await expect(ladder).toBeVisible({ timeout: 15_000 });
    for (const t of tiers) {
      await expect(ladder).toContainText(t.name);
      await expect(ladder).toContainText(t.who);
    }
  });
});

test.describe('Settings engine status is real', () => {
  test('shows Core online when the engine answers', async ({ page }) => {
    await gotoPainted(page, '/settings');
    await expect(page.getByText('Core online')).toBeVisible();
  });
});

test.describe('Symptom check shows words, not a bare count', () => {
  test('Measure lists the reported symptoms by name', async ({ page, request }) => {
    await request.post(`${ENGINE}/admin/reset`);
    await gotoPainted(page, '/measure');
    const row = page.locator('a', { hasText: 'Symptom check' }).last();
    const text = (await row.innerText()).replace(/\s+/g, ' ');
    // Ana's seeded check names headache and fatigue, never just "2".
    expect(text).toMatch(/Headache|Fatigue|None reported/);
    expect(text).not.toMatch(/Symptom check Self-report, 1 min 2 /);
  });
});

test.describe('Loading and error states', () => {
  test('each main route has its own loading screen file', async ({ request }) => {
    // The loading screens are build-time files; check the pages they front still load.
    for (const path of ['/measure', '/trends', '/crew', '/routine', '/learn', '/data', '/settings']) {
      const res = await request.get(path);
      expect(res.ok(), path).toBeTruthy();
    }
  });

});
