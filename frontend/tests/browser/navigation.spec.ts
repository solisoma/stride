import { test, expect } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.route('**/api/backend/**', async route => {
    const path = new URL(route.request().url()).pathname.replace('/api/backend', '');
    let body: unknown;
    if (path === '/auth/me') body = { id: 1, name: 'Test Learner', email: 'test@example.com', role: 'learner' };
    else if (path === '/journeys') body = [{ id: 1, goal: 'exam', subject: 'Algorithms' }];
    else if (path.endsWith('/documents')) body = [{ id: 1, name: 'Study notes', passages: 1 }];
    else if (path.endsWith('/plan')) body = { revision: 1, plan_revision: 1, status: 'ready', topics: [], next: { topic: 'Binary search', action: 'practise', reason: 'Try a new scenario.' }, note: 'Test plan' };
    else if (path.endsWith('/progress')) body = { attempts: [], topics: [], next: { topic: 'Binary search', action: 'practise', reason: 'Try a new scenario.' }, note: 'Test progress' };
    else body = [];
    await route.fulfill({ json: body });
  });
});

const sections = [
  ['Materials', 'materials', 'Build your learning library.'],
  ['Plan', 'plan', 'Your learning map'],
  ['Study', 'study', 'A focused place to start.'],
  ['Practice & chat', 'practice', 'Put your understanding to work.'],
  ['Progress', 'progress', 'Your learning history'],
] as const;

test('journey sections open from dashboard navigation and support back/forward', async ({ page }) => {
  await page.goto('/dashboard');
  await expect(page.getByRole('heading', { name: 'Your journeys', exact: true })).toBeVisible();
  for (const [label, segment, heading] of sections) {
    const link = page.getByRole('navigation').getByRole('link', { name: label, exact: true });
    await expect(link).toHaveAttribute('aria-disabled', 'false');
    await link.click();
    await expect(page).toHaveURL(new RegExp(`/dashboard/journeys/1/${segment}$`));
    await expect(page.getByRole('heading', { name: heading, exact: true })).toBeVisible();
  }
  await page.goBack();
  await expect(page.getByRole('heading', { name: 'Put your understanding to work.', exact: true })).toBeVisible();
  await page.goForward();
  await expect(page.getByRole('heading', { name: 'Your learning history', exact: true })).toBeVisible();
});

for (const [, segment, heading] of sections) {
  test(`direct ${segment} route renders its section after refresh`, async ({ page }) => {
    await page.goto(`/dashboard/journeys/1/${segment}`);
    await expect(page.getByRole('heading', { name: heading, exact: true })).toBeVisible();
    await page.reload();
    await expect(page.getByRole('heading', { name: heading, exact: true })).toBeVisible();
  });
}

test('unknown journey does not render another journey content', async ({ page }) => {
  await page.goto('/dashboard/journeys/999/materials');
  await expect(page.getByRole('heading', { name: 'Journey not available' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Build your learning library.' })).toHaveCount(0);
});


test('refresh shows a skeleton while the session is loading', async ({ page }) => {
  await page.route('**/api/backend/auth/me', async route => {
    await new Promise(resolve => setTimeout(resolve, 1500));
    await route.fulfill({ json: { id: 1, name: 'Test Learner', email: 'test@example.com', role: 'learner' } });
  });
  await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
  await expect(page.getByRole('status', { name: 'Loading your workspace' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Your journeys', exact: true })).toBeVisible();
  await expect(page.getByRole('status', { name: 'Loading your workspace' })).toHaveCount(0);
});


test('API errors display a reference and log safe structured diagnostics', async ({ page }) => {
  const messages: string[] = [];
  page.on('console', message => messages.push(message.text()));
  await page.route('**/api/backend/journeys/1/guides', async route => {
    const reference = route.request().headers()['x-request-id'];
    expect(reference).toBeTruthy();
    await route.fulfill({status: 504, headers: {'X-Request-ID': reference}, json: {detail: 'generation timed out. Retry or check the model endpoint.', error: {code: 'PROVIDER_TIMEOUT', request_id: reference}}});
  });
  await page.goto('/dashboard/journeys/1/study');
  await page.getByLabel('Topic', {exact: true}).fill('private-learner-topic');
  await page.getByRole('button', {name: /Create focused guide/}).click();
  await expect(page.locator('p[role="alert"]')).toContainText('This is taking longer than expected.');
  await expect(page.locator('p[role="alert"]')).toContainText('Reference:');
  await expect(page.locator('p[role="alert"]')).not.toContainText('PROVIDER_TIMEOUT');
  await expect(page.locator('p[role="alert"]')).not.toContainText('model endpoint');
  expect(messages.some(message => message.includes('api_request_failed') && message.includes('PROVIDER_TIMEOUT'))).toBeTruthy();
  expect(messages.filter(message => message.includes('api_request_failed')).join('')).not.toContain('private-learner-topic');
});


test('failed material retries and processing status refreshes to ready', async ({ page }) => {
  let retried = false;
  let polls = 0;
  await page.route('**/api/backend/journeys/1/documents', async route => {
    polls += retried ? 1 : 0;
    const status = !retried ? 'failed' : polls < 2 ? 'queued' : 'ready';
    await route.fulfill({ json: [{ id: 1, name: 'Study notes', passages: status === 'ready' ? 2 : 0,
      status, progress: status === 'queued' ? 'Waiting to resume' : 'Ready',
      error: status === 'failed' ? 'Processing stopped. Please retry.' : '' }] });
  });
  await page.route('**/api/backend/journeys/1/documents/1/retry', async route => {
    retried = true;
    await route.fulfill({ status: 202, json: { id: 1, status: 'queued' } });
  });
  await page.goto('/dashboard/journeys/1/materials');
  await expect(page.getByRole('button', { name: 'Retry processing' })).toBeVisible();
  await page.getByRole('button', { name: 'Retry processing' }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Waiting to resume' })).toBeVisible();
  await expect(page.getByRole('status').filter({ hasText: '2 passages' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Retry processing' })).toHaveCount(0);
});
