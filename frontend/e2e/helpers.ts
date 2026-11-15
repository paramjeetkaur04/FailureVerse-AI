import { test as base, expect, type Page } from '@playwright/test';
import type { Investigation } from '../src/api';

export const test = base.extend<{ browserIssues: string[]; expectedNetworkErrors: Set<string> }>({
  expectedNetworkErrors: async ({}, use) => { await use(new Set()); },
  browserIssues: [async ({ page, expectedNetworkErrors }, use, testInfo) => {
    const issues: string[] = [];
    page.on('pageerror', error => issues.push(`Uncaught: ${error.message}`));
    page.on('console', message => {
      if (!['warning', 'error'].includes(message.type())) return;
      const url = message.location().url;
      const expected = [...expectedNetworkErrors].some(path => url.includes(path));
      if (expected && message.text().startsWith('Failed to load resource:')) return;
      issues.push(`${message.type()}: ${message.text()} (${url})`);
    });
    await use(issues);
    await testInfo.attach('browser-console', {
      body: JSON.stringify({ browser: page.context().browser()?.version(), issues }, null, 2),
      contentType: 'application/json',
    });
    expect(issues, 'Unexpected browser warnings, console errors, or uncaught exceptions').toEqual([]);
  }, { auto: true }],
});
export { expect };

export async function navigate(page: Page, label: string) {
  const menu = page.getByRole('button', { name: 'Open navigation', exact: true });
  if (await menu.isVisible()) await menu.click();
  await page.getByRole('navigation', { name: 'Main navigation' })
    .getByRole('button', { name: label, exact: true }).click();
}

export async function openWorkspace(page: Page) {
  await page.goto('/');
  await expect(page.getByText('Backend connected', { exact: true })).toBeVisible();
}

export async function assertReport(page: Page, run: Investigation) {
  expect(run.report?.grounding_version).toBe('2.1');
  await expect(page.getByRole('heading', { name: 'Investigation report', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Source-validated observations' })).toBeVisible();
  const links = page.locator('.agent-report a[href^="#evidence-"]');
  expect(await links.count()).toBeGreaterThan(0);
  const ids = new Set(run.evidence.map(item => item.id));
  for (const link of await links.all()) {
    const id = await link.getAttribute('title');
    expect(ids.has(id!)).toBe(true);
    await expect(page.locator(`[id="evidence-${id}"]`)).toHaveCount(1);
  }
  const first = links.first();
  const id = await first.getAttribute('title');
  await first.click();
  const evidence = page.locator(`[id="evidence-${id}"]`);
  await expect(evidence).toBeInViewport();
  if (await evidence.getAttribute('open') === null) await evidence.locator('summary').click();
  await expect(evidence.locator('pre')).toContainText(id!);
  const downloadPending = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export JSON', exact: true }).click();
  const download = await downloadPending;
  expect(download.suggestedFilename()).toBe(`failureverse-investigation-${run.id}.json`);
  const stream = await download.createReadStream();
  const chunks: Buffer[] = [];
  for await (const chunk of stream!) chunks.push(Buffer.from(chunk));
  const exported = JSON.parse(Buffer.concat(chunks).toString());
  expect(exported.id).toBe(run.id);
  expect(exported.report).toEqual(run.report);
  expect(exported.evidence).toEqual(run.evidence);
  expect(exported.events).toEqual(run.events);
  expect(exported.status).toBe(run.status);
  expect(exported.model_calls).toBe(run.model_calls);
  expect(exported.tool_calls).toBe(run.tool_calls);
  expect(exported.limits).toEqual(run.limits);
}
