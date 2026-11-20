import { defineConfig } from '@playwright/test';

const baseURL = process.env.FV_E2E_BASE_URL ?? 'http://localhost:8080';
const target = new URL(baseURL);
if (!['localhost', '127.0.0.1', '[::1]'].includes(target.hostname)
    || target.protocol !== 'http:' || target.username || target.password
    || target.pathname !== '/' || target.search || target.hash) {
  throw new Error('Browser verification accepts only a loopback HTTP origin.');
}

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  timeout: 45_000,
  globalTimeout: 20 * 60_000,
  expect: { timeout: 12_000 },
  outputDir: process.env.FV_E2E_LIVE_AI === '1'
    ? '../artifacts/phase3/browser/live-test-results' : '../artifacts/phase3/browser/test-results',
  reporter: [['list'], ['json', {
    outputFile: process.env.FV_E2E_LIVE_AI === '1'
      ? '../artifacts/phase3/browser/live-results.json' : '../artifacts/phase3/browser/results.json',
  }]],
  use: {
    baseURL,
    browserName: 'chromium',
    channel: process.env.FV_E2E_BROWSER_CHANNEL || undefined,
    viewport: { width: 1440, height: 900 },
    actionTimeout: 15_000,
    navigationTimeout: 20_000,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
});
