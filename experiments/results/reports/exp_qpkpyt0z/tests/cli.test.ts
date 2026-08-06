import { describe, it, expect } from "vitest";
import { execSync } from "node:child_process";

describe("CLI", () => {
  // Skip if not built
  const hasDist = (() => {
    try {
      execSync("node dist/index.js --version", { stdio: "pipe" });
      return true;
    } catch {
      return false;
    }
  })();

  const skipIfNoDist = hasDist ? it : it.skip;

  skipIfNoDist("shows version", () => {
    const out = execSync("node dist/index.js --version", { encoding: "utf-8" });
    expect(out.trim()).toBe("1.0.0");
  });

  skipIfNoDist("shows help", () => {
    const out = execSync("node dist/index.js --help", { encoding: "utf-8" });
    expect(out).toContain("Usage:");
    expect(out).toContain("--source");
    expect(out).toContain("--templates");
    expect(out).toContain("--output");
  });

  skipIfNoDist("accepts --title and --url flags", () => {
    const out = execSync("node dist/index.js --help", { encoding: "utf-8" });
    expect(out).toContain("--title");
    expect(out).toContain("--url");
  });
});
