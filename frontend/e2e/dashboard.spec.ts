import { test, expect, navigate, openWorkspace, assertReport } from './helpers';
import type { Investigation, RunSummary } from '../src/api';

const pages = [
  ['Overview', 'Infrastructure overview'],
  ['Infrastructure', 'Service health'],
  ['Health-check history', 'Observation history'],
  ['AI Investigation Center', 'AI Investigation Center'],
  ['Configuration', 'Workspace configuration'],
];

for (const viewport of [
  { width: 1440, height: 900 }, { width: 1024, height: 768 },
  { width: 390, height: 844 }, { width: 360, height: 800 },
]) {
  test(`live navigation and layout at ${viewport.width}x${viewport.height}`, async ({ page }, testInfo) => {
    await page.setViewportSize(viewport);
    await openWorkspace(page);
    for (const [label, heading] of pages) {
      await navigate(page, label);
      await expect(page.getByRole('heading', { name: heading, exact: true, level: 1 })).toBeVisible();
      if (label === 'AI Investigation Center') {
        await expect(page.getByRole('heading', { name: 'Local investigation agent' })).toBeVisible();
      }
      await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth - innerWidth),
        { message: `${label} must fit the ${viewport.width}px viewport` }).toBeLessThanOrEqual(1);
      await page.screenshot({ path: testInfo.outputPath(`${label.replaceAll(' ', '-')}.png`), fullPage: true });
    }
  });
}

test('live health check persists and appears in browser history', async ({ page }) => {
  await openWorkspace(page);
  const pending = page.waitForResponse(response => response.url().endsWith('/api/checks') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Run health check', exact: true }).click();
  const response = await pending;
  expect(response.status()).toBe(201);
  const check = await response.json();
  expect(check.services).toHaveLength(3);
  expect(check.services.every((service: { measurement: string }) => service.measurement === 'actual')).toBe(true);
  await navigate(page, 'Health-check history');
  await expect(page.getByRole('button').filter({ hasText: check.id.slice(0, 8) })).toBeVisible();
  await page.getByRole('button').filter({ hasText: check.id.slice(0, 8) }).click();
  await expect(page.locator('.check-details tbody tr')).toHaveCount(3);
  for (const service of check.services) {
    await expect(page.locator('.check-details')).toContainText(service.detail);
  }
});

test('keyboard skip link reaches the main content', async ({ page }) => {
  await openWorkspace(page);
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Skip to content' })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.locator('#main-content')).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(page.getByRole('button', { name: 'Run health check', exact: true })).toBeFocused();
});

test('browser offline error is visible and retry recovers real data', async ({ page, context, expectedNetworkErrors }) => {
  await openWorkspace(page);
  expectedNetworkErrors.add('/api/');
  await context.setOffline(true);
  try {
    await page.getByRole('button', { name: 'Run health check', exact: true }).click();
    await expect(page.getByRole('alert')).toContainText('Failed to fetch');
    await expect(page.getByRole('alert')).toContainText('Showing the last saved observations.');
  } finally { await context.setOffline(false); }
  await page.getByRole('button', { name: 'Retry connection' }).click();
  await expect(page.getByRole('alert')).toHaveCount(0);
  await expect(page.getByText('Backend connected', { exact: true })).toBeVisible();
});

test('SIMULATED unavailable provider disables investigation creation', async ({ page }) => {
  await page.route('**/api/ai/status', route => route.fulfill({ json: {
    ready: false, enabled: true, state: 'model_unavailable',
    detail: 'SIMULATED browser check: local model unavailable.', model: 'unavailable-test-model',
    active_run_id: null, limits: { model_calls: 4, tool_calls: 6, deadline_seconds: 180 }, targets: [],
  } }));
  await openWorkspace(page);
  await navigate(page, 'AI Investigation Center');
  await expect(page.getByText('SIMULATED browser check: local model unavailable.')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Start investigation' })).toBeDisabled();
});

test('SIMULATED agent API failure is visible and retry recovers', async ({ page, expectedNetworkErrors }) => {
  expectedNetworkErrors.add('/api/ai/status');
  await page.route('**/api/ai/status', route => route.fulfill({ status: 503, json: {
    detail: 'SIMULATED browser check: provider status unavailable.',
  } }));
  await openWorkspace(page);
  await navigate(page, 'AI Investigation Center');
  await expect(page.getByRole('alert')).toContainText('SIMULATED browser check: provider status unavailable.');
  await expect(page.getByRole('button', { name: 'Start investigation' })).toBeDisabled();
  await page.unroute('**/api/ai/status');
  await page.getByRole('button', { name: 'Retry agent connection' }).click();
  await expect(page.getByRole('alert').filter({ hasText: 'SIMULATED browser check' })).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'Local investigation agent' })).toBeVisible();
});

for (const width of [1440, 360]) {
test(`saved actual grounded report renders citations and exports matching JSON at ${width}px`, async ({ page, request }, testInfo) => {
  await page.setViewportSize({ width, height: 900 });
  const response = await request.get('/api/investigations?limit=20');
  expect(response.ok()).toBe(true);
  const runs: RunSummary[] = await response.json();
  let saved: Investigation | undefined;
  for (const summary of runs.filter(run => run.status === 'completed')) {
    const detail = await request.get(`/api/investigations/${summary.id}`);
    const candidate: Investigation = await detail.json();
    if (candidate.report?.grounding_version === '2.1') { saved = candidate; break; }
  }
  test.skip(!saved, 'Requires a saved actual Phase 2.1 report; use FV_E2E_LIVE_AI=1 to create one.');
  await openWorkspace(page);
  await navigate(page, 'AI Investigation Center');
  await expect(page.getByRole('heading', { name: 'Local investigation agent' })).toBeVisible();
  const row = page.locator('.investigation-history-row').filter({ hasText: saved!.question }).first();
  await expect(row).toBeVisible();
  await row.click();
  await assertReport(page, saved!);
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
  await page.screenshot({ path: testInfo.outputPath('actual-report.png'), fullPage: true });
});
}

test('saved historical reports retain the unverified-output warning', async ({ page, request }) => {
  const response = await request.get('/api/investigations?limit=20');
  expect(response.ok()).toBe(true);
  const runs: RunSummary[] = await response.json();
  let saved: Investigation | undefined;
  for (const summary of runs.filter(run => run.status === 'completed')) {
    const detail = await request.get(`/api/investigations/${summary.id}`);
    const candidate: Investigation = await detail.json();
    if (candidate.report && candidate.report.grounding_version !== '2.1') { saved = candidate; break; }
  }
  test.skip(!saved, 'Requires a saved historical report; verification does not fabricate one.');
  await openWorkspace(page);
  await navigate(page, 'AI Investigation Center');
  await expect(page.getByRole('heading', { name: 'Local investigation agent' })).toBeVisible();
  const index = runs.findIndex(run => run.id === saved!.id);
  await page.locator('.investigation-history-row').nth(index).click();
  await expect(page.getByRole('alert')).toContainText('This historical report predates source-field validation');
  await expect(page.getByRole('heading', { name: 'Historical model observations' })).toBeVisible();
});
