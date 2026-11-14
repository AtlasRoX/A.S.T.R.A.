import { test } from '@playwright/test';

test('debug crew card layout', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto('http://localhost:3000/crew');
  // Click launcher to open assistant
  const launcher = page.locator('button[aria-label*="specialist"]');
  if (await launcher.isVisible()) {
    await launcher.click();
  }
  await page.waitForTimeout(600);

  const card2 = page.locator('li[data-crew]').nth(1);
  const head = card2.locator('> div').first();
  const memberName = head.locator('a[class*="memberName"]');
  const small = memberName.locator('small');
  const viewAs = head.locator('> *:last-child');

  console.log('card box at 1280 with assistant open:', await card2.boundingBox());
  console.log('head box at 1280:', await head.boundingBox());
  console.log('memberName box at 1280:', await memberName.boundingBox());
  console.log('small box at 1280:', await small.boundingBox());
  console.log('small text at 1280:', await small.innerText());
  console.log('viewAs box at 1280:', await viewAs.boundingBox());
  console.log('viewAs text at 1280:', await viewAs.innerText());

  const styles = await page.evaluate(() => {
    const card = document.querySelectorAll('li[data-crew]')[1];
    const head = card?.querySelector('div');
    const memberName = head?.querySelector('a:nth-child(2)');
    const small = memberName?.querySelector('small');
    const viewAs = head?.lastElementChild;
    return {
      assistantDataset: document.documentElement.dataset.assistant,
      rosterCols: getComputedStyle(document.querySelector('ul[aria-label="Crew"]')!).gridTemplateColumns,
      cardWidth: getComputedStyle(card!).width,
      headDisplay: head ? getComputedStyle(head).display : '',
      headGridCols: head ? getComputedStyle(head).gridTemplateColumns : '',
      memberNameWidth: memberName ? getComputedStyle(memberName).width : '',
      smallWidth: small ? getComputedStyle(small).width : '',
      viewAsWidth: viewAs ? getComputedStyle(viewAs).width : '',
    };
  });
  console.log('styles at 1280:', styles);

  await page.screenshot({ path: 'crew-1280-assistant.png' });
});
