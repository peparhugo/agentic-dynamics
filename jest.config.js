/** @type {import('jest').Config} */
module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'node',
  roots: ['<rootDir>/src', '<rootDir>/plugins', '<rootDir>/tests'],
  testMatch: ['**/tests/**/*.test.ts'],
};
