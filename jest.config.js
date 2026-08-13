/** @type {import('jest').Config} */
module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'node',
  roots: ['<rootDir>/src'],
  testMatch: ['**/*.test.ts'],
  clearMocks: true,
  // serve.test.ts spins up real HTTP/WebSocket servers and OS-level file watchers; running test
  // files across multiple worker processes intermittently races their native handle teardown
  // against jest-worker's exit grace period. A single worker avoids that race entirely.
  maxWorkers: 1,
};
