import type { APIRequestContext, Page, TestInfo } from '@playwright/test';
import { test, expect, navigate, openWorkspace, assertReport } from './helpers';
import type { Investigation } from '../src/api';

test.describe('actual browser-to-Ollama-to-Docker investigations', () => {
  test.skip(process.env.FV_E2E_LIVE_AI !== '1', 'Opt in with FV_E2E_LIVE_AI=1; requires real local Ollama and Docker.');
  test.setTimeout(250_000);

  async function start(page: Page, question: string) {
    await openWorkspace(page);
    await navigate(page, 'AI Investigation Center');
    await expect(page.getByText('Model ready', { exact: true })).toBeVisible();
    await page.getByLabel('What should the agent investigate?').fill(question);
    const [response] = await Promise.all([
      page.waitForResponse(response => response.url().endsWith('/api/investigations') && response.request().method() === 'POST', { timeout: 20_000 }),
      page.getByRole('button', { name: 'Start investigation' }).click(),
    ]);
    expect(response.status()).toBe(202);
    const run: Investigation = await response.json();
    await expect(page.getByRole('heading', { name: 'Investigation in progress' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Start investigation' })).toBeDisabled();
    return run.id;
  }

  async function waitForRun(request: APIRequestContext, page: Page, id: string,
    ready: (run: Investigation) => boolean, testInfo: TestInfo) {
    const deadline = Date.now() + 195_000;
    while (Date.now() < deadline) {
      const response = await request.get(`/api/investigations/${id}`);
      expect(response.ok()).toBe(true);
      const run: Investigation = await response.json();
      if (ready(run)) return run;
      if (!['queued', 'running'].includes(run.status)) {
        await testInfo.attach('unexpected-terminal-investigation', {
          body: JSON.stringify(run, null, 2), contentType: 'application/json',
        });
        throw new Error(`Investigation ${id} ended as ${run.status}: ${run.error ?? JSON.stringify(run.report?.validation_notes)}`);
      }
      await page.waitForTimeout(1000);
    }
    throw new Error(`Investigation ${id} did not reach the expected condition within the browser verification deadline.`);
  }

  test('creates a live investigation, shows progress and renders a grounded report', async ({ page, request }, testInfo) => {
    const id = await start(page, 'Investigate current demo container health. Inspect container state and check service health.');
    const run = await waitForRun(request, page, id,
      result => ['completed', 'insufficient_evidence'].includes(result.status), testInfo);
    await expect(page.locator('.agent-events')).toContainText('service_health');
    await expect(page.getByRole('heading', { name: 'Investigation report', exact: true })).toBeVisible({ timeout: 190_000 });
    expect(run.status, run.error ?? JSON.stringify(run.report?.validation_notes)).toBe('completed');
    expect(run.report?.outcome).toBe('conclusions');
    expect(run.report?.model_selection_accepted).toBe(true);
    expect(run.model_calls).toBeLessThanOrEqual(run.limits.model_calls);
    expect(run.tool_calls).toBeLessThanOrEqual(run.limits.tool_calls);
    expect(run.evidence.every(item => item.measurement === 'actual')).toBe(true);
    await assertReport(page, run);
    await testInfo.attach('actual-investigation', { body: JSON.stringify(run, null, 2), contentType: 'application/json' });
    await page.screenshot({ path: testInfo.outputPath('live-report.png'), fullPage: true });
  });

  test('cancellation preserves collected evidence and releases the active slot', async ({ page, request }, testInfo) => {
    const id = await start(page, 'Inspect current demo container health and check service health before reporting.');
    await waitForRun(request, page, id, result => ['queued', 'running'].includes(result.status)
      && result.evidence.some(item => item.tool !== 'investigation_scope'), testInfo);
    await page.getByRole('button', { name: 'Cancel investigation', exact: true }).click();
    await expect(page.locator('.run-budget')).toContainText('cancelled');
    await expect(page.getByRole('button', { name: 'Start investigation' })).toBeEnabled();
    const response = await request.get(`/api/investigations/${id}`);
    const run: Investigation = await response.json();
    expect(run.status).toBe('cancelled');
    expect(run.evidence.length).toBeGreaterThan(0);
    await testInfo.attach('actual-cancelled-investigation', { body: JSON.stringify(run, null, 2), contentType: 'application/json' });
  });

  test('unmeasured disk request returns insufficient evidence without a disk percentage', async ({ page, request }, testInfo) => {
    const id = await start(page, 'What is the demo container disk utilization percentage?');
    const run = await waitForRun(request, page, id,
      result => ['completed', 'insufficient_evidence'].includes(result.status), testInfo);
    await expect(page.getByRole('heading', { name: 'Investigation report', exact: true })).toBeVisible({ timeout: 190_000 });
    expect(run.status).toBe('insufficient_evidence');
    expect(run.report?.outcome).toBe('insufficient_evidence');
    await expect(page.getByRole('alert').filter({ hasText: 'Insufficient evidence for a validated model conclusion.' })).toBeVisible();
    expect(run.report?.observations.some(item => /disk.*\d+(?:\.\d+)?\s*%/i.test(item.statement))).toBe(false);
    await assertReport(page, run);
    await testInfo.attach('actual-insufficient-investigation', { body: JSON.stringify(run, null, 2), contentType: 'application/json' });
  });
});
