import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

test('real PDF journey displays saved materials, plan, study and progress on mobile', async ({ page }) => {
  test.skip(process.env.STRIDE_LIVE_TEST !== 'true', 'Requires the running Docker API and completed live-PDF verification.');
  const root = resolve(process.cwd(), '../backend/.mvp-validation/live');
  const credentials = JSON.parse(readFileSync(resolve(root, 'demo-login.json'), 'utf8'));
  const report = JSON.parse(readFileSync(resolve(root, 'report.json'), 'utf8'));
  await page.goto('/login');
  await page.getByLabel('Email', { exact: true }).fill(credentials.email);
  await page.getByLabel('Password', { exact: true }).fill(credentials.password);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await page.setViewportSize({ width: 390, height: 844 });
  const prefix = `/dashboard/journeys/${report.journey_id}`;
  for (const [route, heading] of [
    ['materials', 'Build your learning library.'],
    ['plan', 'Your learning map'],
    ['study', 'A focused place to start.'],
    ['practice', 'Put your understanding to work.'],
    ['progress', 'Your learning history'],
  ]) {
    await page.goto(`${prefix}/${route}`);
    await expect(page.getByRole('heading', { name: heading, exact: true })).toBeVisible();
    await expect(page.locator('p[role="alert"]')).toHaveCount(0);
    if (route === 'materials') await expect(page.locator('.material-list')).toContainText('Erran-business-summary.pdf');
    if (route === 'study') {
      await page.getByText('Saved guides', { exact: true }).click();
      await expect(page.locator('.saved-guide').first()).toBeVisible();
    }
    if (route === 'progress') {
      await page.locator('details.attempt').first().locator(':scope > summary').click();
      await expect(page.locator('details.attempt').first()).toContainText('I do not know.');
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), 'Expanded feedback must fit mobile').toBeTruthy();
      await page.reload();
      await expect(page.locator('details.attempt').first()).toBeVisible();
    }
    const fits = await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);
    expect(fits, `${route} must fit a mobile viewport`).toBeTruthy();
  }
});
