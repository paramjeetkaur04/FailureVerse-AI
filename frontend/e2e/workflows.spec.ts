import type { APIRequestContext, Page, TestInfo } from '@playwright/test';
import type { AgentWorkflow } from '../src/api';
import { test, expect, navigate, openWorkspace } from './helpers';

async function start(page: Page, investigateHealthy = false) {
  await openWorkspace(page);
  await navigate(page, 'Agent workflows');
  await expect(page.getByRole('heading', { name: 'Coordinated agent workflow' })).toBeVisible();
  await page.getByLabel('What should the workflow investigate?').fill('Investigate current demo container health.');
  await page.getByRole('checkbox', { name: 'Investigate even when monitoring checks are healthy' }).setChecked(investigateHealthy);
  await expect(page.getByRole('button', { name: 'Start workflow', exact: true })).toBeEnabled({ timeout: 30_000 });
  const [response] = await Promise.all([
    page.waitForResponse(response => response.url().endsWith('/api/workflows') && response.request().method() === 'POST', { timeout: 20_000 }),
    page.getByRole('button', { name: 'Start workflow', exact: true }).click(),
  ]);
  expect(response.status()).toBe(202);
  const run: AgentWorkflow = await response.json();
  return run.id;
}

async function waitForRun(request: APIRequestContext, page: Page, id: string, ready: (run: AgentWorkflow) => boolean) {
  const deadline = Date.now() + 320_000;
  while (Date.now() < deadline) {
    const response = await request.get(`/api/workflows/${id}`);
    expect(response.ok()).toBe(true);
    const run: AgentWorkflow = await response.json();
    if (ready(run)) return run;
    if (!['queued', 'running'].includes(run.status)) throw new Error(`Workflow ended ${run.status}: ${run.error}`);
    await page.waitForTimeout(1000);
  }
  throw new Error('Workflow did not finish within its persisted deadline and verification allowance.');
}

async function verifyExportAndCitations(page: Page, run: AgentWorkflow) {
  await expect(page.getByRole('heading', { name: 'Workflow result', exact: true })).toBeVisible();
  const ids = new Set(run.checkpoint.evidence.map(item => item.id));
  const links = page.locator('a[href^="#workflow-evidence-"]');
  expect(await links.count()).toBeGreaterThan(0);
  for (const link of await links.all()) {
    const id = await link.getAttribute('title');
    expect(ids.has(id!)).toBe(true);
    await expect(page.locator(`[id="workflow-evidence-${id}"]`)).toHaveCount(1);
  }
  const first = links.first();
  const id = await first.getAttribute('title');
  await first.click();
  const evidence = page.locator(`[id="workflow-evidence-${id}"]`);
  await expect(evidence).toBeInViewport();
  if (await evidence.getAttribute('open') === null) await evidence.locator('summary').click();
  await expect(evidence.locator('pre')).toContainText(id!);
  const pending = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export workflow JSON' }).click();
  const download = await pending;
  const stream = await download.createReadStream();
  const chunks: Buffer[] = [];
  for await (const chunk of stream!) chunks.push(Buffer.from(chunk));
  expect(JSON.parse(Buffer.concat(chunks).toString())).toEqual(run);
  await expect(page.getByRole('button', { name: /execute|approve|restart/i })).toHaveCount(0);
}

test('actual healthy workflow uses zero inference and exports cited monitoring evidence', async ({ page, request }, testInfo) => {
  const id = await start(page);
  const run = await waitForRun(request, page, id, run => !['queued', 'running'].includes(run.status));
  expect(run.status, run.error ?? '').toBe('observed_healthy');
  expect(run.checkpoint.model_calls).toBe(0);
  expect(run.checkpoint.tool_calls).toBe(3);
  expect(run.checkpoint.monitoring?.signals).toEqual([]);
  expect(run.checkpoint.evidence.every(item => item.measurement === 'actual')).toBe(true);
  await expect(page.getByText('skipped', { exact: true })).toHaveCount(4);
  await verifyExportAndCitations(page, run);
  await testInfo.attach('actual-monitoring-workflow', { body: JSON.stringify(run, null, 2), contentType: 'application/json' });
});

test('SIMULATED workflow API error is visible and retry recovers the actual list', async ({ page, expectedNetworkErrors }) => {
  expectedNetworkErrors.add('/api/workflows');
  await page.route('**/api/workflows', route => route.fulfill({ status: 503, json: { detail: 'SIMULATED workflow storage unavailable.' } }));
  await openWorkspace(page);
  await navigate(page, 'Agent workflows');
  await expect(page.getByRole('alert')).toContainText('SIMULATED workflow storage unavailable.');
  await page.unroute('**/api/workflows');
  await page.getByRole('button', { name: 'Retry workflow connection' }).click();
  await expect(page.getByRole('alert').filter({ hasText: 'SIMULATED workflow storage unavailable.' })).toHaveCount(0);
});

test.describe('actual Phase 3 local-model coordination', () => {
  test.skip(process.env.FV_E2E_LIVE_AI !== '1', 'Requires actual local Ollama; no scripted replacement.');
  test.setTimeout(390_000);

  test('forced healthy workflow completes all roles with proposed actions remaining inert', async ({ page, request }, testInfo) => {
    const id = await start(page, true);
    await expect(page.getByRole('heading', { name: 'Workflow in progress' })).toBeVisible();
    const run = await waitForRun(request, page, id, run => !['queued', 'running'].includes(run.status));
    expect(run.status, run.error ?? '').toBe('awaiting_review');
    expect(run.checkpoint.investigation?.model_selection_accepted).toBe(true);
    expect(run.checkpoint.model_calls).toBeLessThanOrEqual(7);
    expect(run.checkpoint.tool_calls).toBeLessThanOrEqual(9);
    expect(run.checkpoint.role_models.risk ?? 0).toBe(0);
    expect(run.execution_enabled).toBe(false);
    await expect(page.getByRole('heading', { name: 'Recovery planning' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Risk analysis' })).toBeVisible();
    await verifyExportAndCitations(page, run);
    await testInfo.attach('actual-coordinated-workflow', { body: JSON.stringify(run, null, 2), contentType: 'application/json' });
    await page.screenshot({ path: testInfo.outputPath('phase3-workflow.png'), fullPage: true });
  });

  test('actual workflow cancellation preserves checkpoint evidence and releases the shared slot', async ({ page, request }) => {
    const id = await start(page, true);
    await waitForRun(request, page, id, run => run.checkpoint.next_stage === 'investigation' && run.checkpoint.evidence.length > 0);
    await page.getByRole('button', { name: 'Cancel workflow', exact: true }).click();
    await expect(page.locator('.run-budget')).toContainText('cancelled');
    await expect(page.getByRole('button', { name: 'Start workflow', exact: true })).toBeEnabled({ timeout: 20_000 });
    const response = await request.get(`/api/workflows/${id}`);
    const run: AgentWorkflow = await response.json();
    expect(run.status).toBe('cancelled');
    expect(run.checkpoint.evidence.length).toBeGreaterThan(0);
    expect(run.resumable).toBe(false);
  });
});
