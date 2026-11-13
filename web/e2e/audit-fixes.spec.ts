import { test, expect, type APIRequestContext } from '@playwright/test';
import { gotoPainted } from './helpers';

const ENGINE = 'http://127.0.0.1:8000';

async function cleanup(request: APIRequestContext) {
  await request.post(`${ENGINE}/sim/live/stop`);
  await request.post(`${ENGINE}/admin/reset`);
}

test.describe('Tab lists work with the keyboard', () => {
  test('Trends time range: arrows, Home and End move focus between the tabs', async ({ page }) => {
    await gotoPainted(page, '/trends');
    const tabs = page.getByRole('tablist', { name: 'Time range' }).getByRole('tab');
    await tabs.first().focus();
    await page.keyboard.press('ArrowRight');
    await expect(tabs.nth(1)).toBeFocused();
    await page.keyboard.press('End');
    await expect(tabs.last()).toBeFocused();
    await page.keyboard.press('Home');
    await expect(tabs.first()).toBeFocused();
    await page.keyboard.press('ArrowLeft'); // wraps to the last
    await expect(tabs.last()).toBeFocused();
  });

  test('the trend chart slider supports Home and End', async ({ page }) => {
    await gotoPainted(page, '/trends');
    const slider = page.getByRole('slider').first();
    await slider.focus();
    await page.keyboard.press('End');
    const last = await slider.getAttribute('aria-valuenow');
    await page.keyboard.press('Home');
    expect(await slider.getAttribute('aria-valuenow')).toBe('0');
    expect(Number(last)).toBeGreaterThan(0);
  });
});

test.describe('Light theme status chips meet 4.5:1', () => {
  test.use({ colorScheme: 'light' });

  test('every Nominal / Watch / Act chip on the Overview and Measure pages', async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem('astra-theme', 'light'));
    for (const path of ['/', '/measure', '/crew']) {
      await gotoPainted(page, path);
      const results = await page.evaluate(() => {
        const parse = (c: string) => {
          const m = c.match(/rgba?\(([^)]+)\)/);
          if (!m) return null;
          const [r, g, b, alpha] = m[1].split(/[ ,/]+/).filter(Boolean).map(Number);
          return { r, g, b, a: alpha === undefined || Number.isNaN(alpha) ? 1 : alpha };
        };
        const lin = (v: number) => {
          const c = v / 255;
          return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
        };
        const lum = (c: { r: number; g: number; b: number }) => 0.2126 * lin(c.r) + 0.7152 * lin(c.g) + 0.0722 * lin(c.b);
        const over = (fg: { r: number; g: number; b: number; a: number }, bg: { r: number; g: number; b: number }) => ({
          r: fg.a * fg.r + (1 - fg.a) * bg.r,
          g: fg.a * fg.g + (1 - fg.a) * bg.g,
          b: fg.a * fg.b + (1 - fg.a) * bg.b,
        });
        const backdrop = (el: Element) => {
          let bg = { r: 255, g: 255, b: 255 };
          const chain: Element[] = [];
          for (let n: Element | null = el; n; n = n.parentElement) chain.unshift(n);
          for (const n of chain) {
            const c = parse(getComputedStyle(n).backgroundColor);
            if (c && c.a > 0) bg = over(c, bg);
          }
          return bg;
        };
        const out: string[] = [];
        document.querySelectorAll('.chip-ok, .chip-watch, .chip-act').forEach((el) => {
          const r = el.getBoundingClientRect();
          if (!r.width) return;
          const fg = parse(getComputedStyle(el).color);
          if (!fg) return;
          const bg = backdrop(el);
          const l1 = lum(over(fg, bg));
          const l2 = lum(bg);
          const ratio = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
          if (ratio < 4.5) out.push(`${(el as HTMLElement).innerText.trim()} ${ratio.toFixed(2)}`);
        });
        return out;
      });
      expect(results, `${path}: ${results.join('; ')}`).toEqual([]);
    }
  });
});

test.describe('Telemetry is labelled honestly', () => {
  test('the radiation card says a modelled dose rate is not a NASA measurement', async ({ page, request }) => {
    try {
      await request.post(`${ENGINE}/admin/reset`);
      await request.post(`${ENGINE}/sim/live/start`, {
        data: { scenario: 'solar_storm', interval_s: 3600, crew_id: 'ana' },
      });
      await request.post(`${ENGINE}/sim/live/tick`);
      await request.post(`${ENGINE}/sim/live/tick`);
      await gotoPainted(page, '/');
      await expect(page.getByText(/dose rate comes from ASTRA's live model, not from a NASA measurement/i)).toBeVisible();
      await expect(page.getByText('MSL/RAD · measured dose rate')).toHaveCount(0);
    } finally {
      await cleanup(request);
    }
  });

  test('an Act telemetry reading raises one packet, without the word simulated', async ({ request }) => {
    try {
      await request.post(`${ENGINE}/admin/reset`);
      await request.post(`${ENGINE}/sim/live/start`, {
        data: { scenario: 'exercise', interval_s: 3600, crew_id: 'kenji' },
      });
      for (let i = 0; i < 4; i += 1) await request.post(`${ENGINE}/sim/live/tick`);
      const comms = await (await request.get(`${ENGINE}/comms?env=transit&crew_id=kenji`)).json();
      const sim = [...comms.cmo, ...comms.ground].filter((p: { title: string; body: string }) => p.body.includes('From live telemetry'));
      expect(sim.length).toBeGreaterThan(0);
      await request.post(`${ENGINE}/sim/live/tick`);
      const again = await (await request.get(`${ENGINE}/comms?env=transit&crew_id=kenji`)).json();
      const simAgain = [...again.cmo, ...again.ground].filter((p: { title: string; body: string }) => p.body.includes('From live telemetry'));
      expect(simAgain.length).toBe(sim.length);
    } finally {
      await cleanup(request);
    }
  });
});
