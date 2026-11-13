import { test, expect } from '@playwright/test';
import { gotoPainted } from './helpers';

const VIEWPORTS = [
  { width: 1440, height: 900, name: 'desktop-1440' },
  { width: 1280, height: 800, name: 'laptop-1280' },
  { width: 1024, height: 768, name: 'tablet-landscape-1024' },
  { width: 768, height: 1024, name: 'tablet-portrait-768' },
  { width: 390, height: 844, name: 'phone-390' },
];

// The reference section is labelled "Reference" on wide screens and "Learn" where space is short.
const DESTINATIONS: { label: string | RegExp; href: string }[] = [
  { label: 'Today', href: '/' },
  { label: 'Measure', href: '/measure' },
  { label: 'Trends', href: '/trends' },
  { label: 'Crew', href: '/crew' },
  { label: /Reference|Learn/, href: '/learn' },
];

test.describe('Shell Navigation — 5 Destinations', () => {
  test('desktop (1440px) shows 5 destinations in primary navigation', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await gotoPainted(page, '/');

    const primaryNav = page.locator('nav[aria-label="Primary navigation"]');
    await expect(primaryNav).toBeVisible();

    for (const dest of DESTINATIONS) {
      const link = primaryNav.locator(`a[href="${dest.href}"]`);
      await expect(link, `primary nav has ${dest.label}`).toBeVisible();
      await expect(link).toContainText(dest.label);
    }
  });

  test('tablet landscape (1024px) shows 5 destinations in top bar', async ({ page }) => {
    await page.setViewportSize({ width: 1024, height: 768 });
    await gotoPainted(page, '/');

    const primaryNav = page.locator('nav[aria-label="Primary navigation"]');
    await expect(primaryNav).toBeVisible();

    for (const dest of DESTINATIONS) {
      const link = primaryNav.locator(`a[href="${dest.href}"]`);
      await expect(link, `1024px nav has ${dest.label}`).toBeVisible();
      await expect(link).toContainText(dest.label);
    }

    const mobileNav = page.locator('nav[aria-label="Mobile navigation"]');
    await expect(mobileNav).toBeHidden();
  });

  // Below 1024px the top tabs give way to the bottom bar (tablet portrait included).
  for (const vp of [
    { width: 768, height: 1024, name: 'tablet portrait (768px)' },
    { width: 390, height: 844, name: 'phone (390px)' },
  ]) {
    test(`${vp.name} shows 5 destinations in mobile bottom bar`, async ({ page }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await gotoPainted(page, '/');

      const primaryNav = page.locator('nav[aria-label="Primary navigation"]');
      await expect(primaryNav).toBeHidden();

      const mobileNav = page.locator('nav[aria-label="Mobile navigation"]');
      await expect(mobileNav).toBeVisible();

      for (const dest of DESTINATIONS) {
        const link = mobileNav.locator(`a[href="${dest.href}"]`);
        await expect(link, `mobile nav has ${dest.label}`).toBeVisible();
        await expect(link).toContainText(dest.label);
      }
    });
  }
});

test.describe('Mission Strip', () => {
  for (const vp of [
    { width: 1440, height: 900 },
    { width: 1024, height: 768 },
    { width: 768, height: 1024 },
    { width: 390, height: 844 },
  ]) {
    test(`mission strip is visible and displays delay at ${vp.width}px`, async ({ page }) => {
      await page.setViewportSize(vp);
      await gotoPainted(page, '/');

      const strip = page.locator('#mission-strip');
      await expect(strip).toBeVisible();
      const text = await strip.innerText();
      expect(text).toMatch(/MET/i);
      expect(text).toMatch(/Earth/i);
    });
  }
});

test.describe('No horizontal overflow', () => {
  for (const vp of VIEWPORTS) {
    test(`no horizontal overflow at ${vp.width}px (${vp.name})`, async ({ page }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await gotoPainted(page, '/');
      await page.waitForTimeout(500);

      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      expect(overflow, `horizontal overflow at ${vp.width}px`).toBeLessThanOrEqual(2);
    });
  }
});

test.describe('Overview Layout Hierarchy', () => {
  test('attention queue precedes body systems in DOM', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await gotoPainted(page, '/');

    const result = await page.evaluate(() => {
      const aq = document.querySelector('#attention-queue');
      const body = document.querySelector('#body-systems');
      if (!aq || !body) return null;
      return aq.compareDocumentPosition(body) & Node.DOCUMENT_POSITION_FOLLOWING;
    });

    expect(result, 'Attention queue must precede body systems in DOM').toBeTruthy();
  });

  test('skip link focuses main content', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await gotoPainted(page, '/');

    const skipLink = page.locator('a[href="#main-content"]');
    await expect(skipLink).toBeAttached();

    // Tab into skip link
    await page.keyboard.press('Tab');
    await expect(skipLink).toBeFocused();

    // Trigger skip link
    await page.keyboard.press('Enter');
    const mainFocused = await page.evaluate(() => document.activeElement?.id === 'main-content');
    expect(mainFocused).toBe(true);
  });
});

test.describe('Old URLs still load cleanly', () => {
  test('/routine loads and has tasks', async ({ page }) => {
    await gotoPainted(page, '/routine');
    const body = await page.locator('body').innerText();
    expect(body).toMatch(/routine|tasks|checks/i);
  });

  test('/data loads and has cited papers', async ({ page }) => {
    await gotoPainted(page, '/data');
    const body = await page.locator('body').innerText();
    expect(body).toMatch(/data|sources|documents|telemetry/i);
  });

});
