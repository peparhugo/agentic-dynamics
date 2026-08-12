/** @type {import('jest').Config} */
module.exports = {
  testEnvironment: "node",
  roots: ["<rootDir>/src"],
  testMatch: ["**/__tests__/**/*.test.ts"],
  transform: {
    "^.+\\.(t|j)sx?$": ["@swc/jest", {
      jsc: {
        parser: { syntax: "typescript" },
      },
      module: {
        type: "commonjs",
      },
    }],
  },
  transformIgnorePatterns: [],
};
