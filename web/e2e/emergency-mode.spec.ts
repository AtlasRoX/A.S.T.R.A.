import { test, expect } from '@playwright/test';

test('Emergency mode: full-screen, 1-step, metronome, hold-to-end, drill flow', async ({ page }) => {
  // Test on tablet 1024x768
  await page.setViewportSize({ width: 1024, height: 768 });
  await page.goto('/emergency', { waitUntil: 'networkidle' });

  // 1. Pick screen: check "Run as drill"
  const drillCheckbox = page.locator('input#run-as-drill');
  await expect(drillCheckbox).toBeVisible();
  await drillCheckbox.check();

  const startBtn = page.getByRole('button', { name: /start drill/i });
  await expect(startBtn).toBeVisible();

  // Capture before screenshot at 1024x768
  await page.screenshot({ path: '../docs/ux/screens/emergency-mode-tablet-pick.png' });

  // Start drill
  await startBtn.click();
  await page.waitForTimeout(600);

  // 2. Run mode: verify full-screen landmark, red band, no app nav
  const runner = page.getByRole('region', { name: /emergency protocol runner/i });
  await expect(runner).toBeVisible();
  await expect(page.getByText('TRAINING DRILL')).toBeVisible();

  // App navigation tabs must NOT be visible during run mode
  const mainNav = page.locator('nav[aria-label="Main navigation"]');
  await expect(mainNav).toBeHidden();

  // Verify ONE step at a time: Step 1
  await expect(page.locator('span[class*="stepCounter"]').filter({ hasText: /STEP 1 of/i })).toBeVisible();
  await expect(page.getByRole('heading', { name: /call it out/i })).toBeVisible();

  // Capture running screenshot at 1024x768
  await page.screenshot({ path: '../docs/ux/screens/emergency-mode-tablet-run.png' });

  // 3. Advance 2 steps
  const doneBtn = page.getByRole('button', { name: /^done/i });
  await doneBtn.click();
  await page.waitForTimeout(200);

  // Now Step 2
  await expect(page.locator('span[class*="stepCounter"]').filter({ hasText: /STEP 2 of/i })).toBeVisible();
  await expect(page.getByRole('heading', { name: /secure patient and rescuer/i })).toBeVisible();

  await doneBtn.click();
  await page.waitForTimeout(200);

  // Now Step 3
  await expect(page.locator('span[class*="stepCounter"]').filter({ hasText: /STEP 3 of/i })).toBeVisible();

  // 4. Reopen a done step
  const stepsSoFarBtn = page.getByRole('button', { name: /steps so far/i });
  await expect(stepsSoFarBtn).toBeVisible();
  await stepsSoFarBtn.click({ force: true });
  await page.waitForTimeout(300);

  // Click on done Step 1 inside the done list to reopen it
  const step1Item = page.locator('#done-steps-list button').filter({ hasText: /call it out/i });
  await expect(step1Item).toBeVisible();
  await step1Item.click({ force: true });
  await page.waitForTimeout(300);

  // Verify Step 1 is active again
  await expect(page.locator('span[class*="stepCounter"]').filter({ hasText: /STEP 1 of/i })).toBeVisible();
  await expect(page.getByRole('heading', { name: /call it out/i })).toBeVisible();

  // 5. Switch track
  const trackBtn = page.getByRole('radio', { name: /conscious, chest pain/i });
  await expect(trackBtn).toBeVisible();
  await trackBtn.click();
  await expect(trackBtn).toHaveAttribute('aria-checked', 'true');

  // 6. Test deliberate action: single tap does NOT end protocol
  const endBtn = page.getByRole('button', { name: /hold 1 second to end/i });
  await expect(endBtn).toBeVisible();

  // Quick tap
  await endBtn.click();
  await page.waitForTimeout(200);

  // Confirm box appears, protocol did NOT end
  await expect(page.getByText(/end protocol early\?/i)).toBeVisible();
  const keepRunningBtn = page.getByRole('button', { name: /keep running/i });
  await expect(keepRunningBtn).toBeVisible();
  await keepRunningBtn.click();

  // Protocol is still running
  await expect(page.getByText('TRAINING DRILL')).toBeVisible();

  // 7. Press-and-hold ~1 second ends the protocol
  const endBox = await endBtn.boundingBox();
  expect(endBox).not.toBeNull();

  await page.mouse.move(endBox!.x + endBox!.width / 2, endBox!.y + endBox!.height / 2);
  await page.mouse.down();
  await page.waitForTimeout(1150);
  await page.mouse.up();
  await page.waitForTimeout(600);

  // 8. Completion screen: verify truthful text
  await expect(page.getByRole('heading', { name: /drill ended early/i })).toBeVisible();
  await expect(
    page.getByText(/Drill ended early\. A practice record \(duration and number of steps\) was sent to Mission Control\./i)
  ).toBeVisible();

  // Capture done screenshot at 1024x768
  await page.screenshot({ path: '../docs/ux/screens/emergency-mode-tablet-done.png' });
});

test('Emergency mode: mobile phone 390x844 layout & thumb zone', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/emergency', { waitUntil: 'networkidle' });

  // Mobile bottom nav must not be rendered
  const mobileNav = page.locator('nav[aria-label="Mobile navigation"]');
  await expect(mobileNav).toHaveCount(0);

  // Capture mobile picker screenshot
  await page.screenshot({ path: '../docs/ux/screens/emergency-mode-mobile-pick.png' });

  // Start protocol
  const startBtn = page.getByRole('button', { name: /start protocol/i });
  await startBtn.click();
  await page.waitForTimeout(600);

  // Verify emergency header in red band
  await expect(page.getByText(/EMERGENCY · ACT/i)).toBeVisible();

  // Verify Done / Back actions are reachable in thumb zone
  const doneBtn = page.getByRole('button', { name: /^done/i });
  await expect(doneBtn).toBeVisible();
  const doneBox = await doneBtn.boundingBox();
  expect(doneBox).not.toBeNull();
  expect(doneBox!.y + doneBox!.height).toBeLessThanOrEqual(844);

  // Verify Earth bar is visible at bottom
  const earthBar = page.locator('footer');
  await expect(earthBar).toBeVisible();
  await expect(page.getByText(/Completion: not sent yet/i)).toBeVisible();

  // Capture mobile running screenshot
  await page.screenshot({ path: '../docs/ux/screens/emergency-mode-mobile-run.png' });
});

test('Emergency mode: responsive viewports 768x1024 and 1440x900 without horizontal scroll', async ({ page }) => {
  // Test tablet portrait 768x1024
  await page.setViewportSize({ width: 768, height: 1024 });
  await page.goto('/emergency', { waitUntil: 'networkidle' });

  const startBtn = page.getByRole('button', { name: /start protocol/i });
  await startBtn.click();
  await page.waitForTimeout(600);

  // Check no horizontal scroll on container
  const scrollWidth768 = await page.evaluate(() => document.documentElement.scrollWidth);
  expect(scrollWidth768).toBeLessThanOrEqual(768);

  // Capture tablet portrait screenshot
  await page.screenshot({ path: '../docs/ux/screens/emergency-mode-768-run.png' });

  // Test desktop 1440x900
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.waitForTimeout(300);

  const scrollWidth1440 = await page.evaluate(() => document.documentElement.scrollWidth);
  expect(scrollWidth1440).toBeLessThanOrEqual(1440);

  // Capture desktop screenshot
  await page.screenshot({ path: '../docs/ux/screens/emergency-mode-1440-run.png' });
});
