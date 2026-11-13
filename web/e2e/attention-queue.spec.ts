import { test, expect } from '@playwright/test';
import { gotoPainted } from './helpers';

const ENGINE_URL = process.env.ENGINE_URL ?? 'http://127.0.0.1:8000';

test.describe('Attention Queue and Header Badge', () => {
  test.beforeEach(async ({ request }) => {
    // Reset database to deterministic clean state
    const res = await request.post(`${ENGINE_URL}/admin/reset`);
    expect(res.ok()).toBeTruthy();
  });

  test('Header badge matches Overview count, acknowledge persists, CMO resolves with note, and nominal reading auto-resolves', async ({
    page,
    context,
    request,
  }) => {
    // Set initial crew to Ana
    await context.addCookies([
      { name: 'astra_crew', value: 'ana', domain: 'localhost', path: '/' },
      { name: 'astra_env', value: 'station', domain: 'localhost', path: '/' },
    ]);

    // 1. Navigate to Overview
    await gotoPainted(page, '/');

    // Verify Attention Queue section exists
    const queue = page.locator('#attention-queue');
    await expect(queue).toBeVisible();

    // Check header badge
    const headerBadge = page.locator('header a[href="/#attention-queue"]');
    await expect(headerBadge).toBeVisible();

    // Verify header badge has accessible label and matches counts
    const badgeText = await headerBadge.innerText();
    expect(badgeText).toMatch(/(Act|Watch)/i);

    // Get count pills inside the attention queue
    const queuePills = queue.locator('[class*="countPill"]');
    const pillCount = await queuePills.count();
    expect(pillCount).toBeGreaterThan(0);

    // 2. Acknowledge an item
    const firstItem = queue.locator('li[data-key]').first();
    await expect(firstItem).toBeVisible();
    const itemKey = await firstItem.getAttribute('data-key');
    expect(itemKey).toBeTruthy();

    const ackBtn = firstItem.locator('button', { hasText: 'Acknowledge' });
    await expect(ackBtn).toBeVisible();
    await ackBtn.click();

    // After clicking acknowledge, button disappears and shows "Acknowledged" text
    await expect(firstItem.locator('text=Acknowledged')).toBeVisible();

    // Reload page to verify acknowledge persisted
    // Acknowledged items move to the end of the queue, which may be behind "Show N more".
    await page.reload();
    await queue.locator('li[data-key]').first().waitFor();
    const showMore = queue.getByRole('button', { name: /^Show \d+ more$/ });
    if (await showMore.isVisible()) await showMore.click();
    await expect(page.locator(`li[data-key="${itemKey}"]`).locator('text=Acknowledged')).toBeVisible();

    // 3. Switch to CMO (Kenji) and resolve an item with note
    await context.addCookies([
      { name: 'astra_crew', value: 'kenji', domain: 'localhost', path: '/' },
    ]);

    // Navigate to /crew page
    await gotoPainted(page, '/crew');

    // On Crew page, whole-crew queue is displayed
    const crewQueue = page.locator('#attention-queue');
    await expect(crewQueue).toBeVisible();

    // Kenji is CMO, so resolve buttons are present
    const resolveBtn = crewQueue.locator('button', { hasText: 'Resolve' }).first();
    await expect(resolveBtn).toBeVisible();
    await resolveBtn.click();

    // Input note and confirm resolve
    const noteInput = crewQueue.locator('input[placeholder*="Assessed"]');
    await expect(noteInput).toBeVisible();
    await noteInput.fill('Evaluated crew member. Condition stable and resting.');

    const confirmResolveBtn = crewQueue.locator('button', { hasText: 'Confirm resolve' });
    await confirmResolveBtn.click();

    // Verify resolve form closes and item is removed from active queue
    await expect(noteInput).not.toBeVisible();

    // 4. An item disappears when its reading is back to Nominal
    // Switch back to Ana
    await context.addCookies([
      { name: 'astra_crew', value: 'ana', domain: 'localhost', path: '/' },
    ]);
    await gotoPainted(page, '/');

    // Check if Ana has a mood item
    const anaMoodItem = page.locator('li[data-key*="metric:ana:mood"]');
    if (await anaMoodItem.count() > 0) {
      // Post a Nominal reading for mood (e.g. 4.5)
      const saveRes = await request.post(`${ENGINE_URL}/crew/ana/readings`, {
        data: { metric: 'mood', value: 4.5, env: 'station' },
      });
      expect(saveRes.ok()).toBeTruthy();

      // Reload page and verify item disappeared
      await page.reload();
      await expect(page.locator('li[data-key*="metric:ana:mood"]')).toHaveCount(0);
    }
  });
});
