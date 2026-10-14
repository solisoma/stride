import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/browser',
  workers: 1,
  timeout: 180000,
  expect: { timeout: 30000 },
  use: { baseURL: 'http://127.0.0.1:3107', channel: 'msedge', headless: true, trace: 'retain-on-failure' },
  webServer: {
    command: 'node node_modules/next/dist/bin/next dev --hostname 127.0.0.1 --port 3107',
    url: 'http://127.0.0.1:3107',
    env: { LEARNFORWARD_TEST_DIST_DIR: '.next-e2e' },
    reuseExistingServer: false,
    timeout: 120000,
  },
});
