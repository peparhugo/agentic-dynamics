import { describe, it, expect, beforeAll, afterAll } from "vitest";
import { spawnSync } from "node:child_process";
import { resolve } from "node:path";
import { mkdtempSync, rmSync } from "node:fs";

const CLI = resolve("src/index.ts");
const runner = process.execPath;

function run(...args: string[]) {
  return spawnSync(runner, ["--import", "tsx", CLI, ...args], {
    encoding: "utf-8",
    cwd: resolve("."),
    env: { ...process.env },
  });
}

describe("CLI", () => {
  describe("build command", () => {
    it("accepts --src, --tmpl, --out flags", () => {
      const out = mkdtempSync("/tmp/ssg-build-");
      try {
        const r = run(
          "build",
          "--src", resolve("tests/fixtures/content"),
          "--tmpl", resolve("tests/fixtures/templates"),
          "--out", out,
          "--title", "TestSite",
        );
        expect(r.status).toBe(0);
      } finally {
        rmSync(out, { recursive: true, force: true });
      }
    });

    it("uses default values when flags omitted", () => {
      const p = run("build", "--help");
      expect(p.stdout).toContain("--src");
      expect(p.stdout).toContain("content");
    });

    it("accepts --base-url and --description", () => {
      const out = mkdtempSync("/tmp/ssg-build-2-");
      try {
        const r = run(
          "build",
          "--src", resolve("tests/fixtures/content"),
          "--tmpl", resolve("tests/fixtures/templates"),
          "--out", out,
          "--base-url", "https://example.com",
          "--description", "A nice site",
        );
        expect(r.status).toBe(0);
      } finally {
        rmSync(out, { recursive: true, force: true });
      }
    });
  });

  describe("serve command", () => {
    it("accepts --out and --port flags", () => {
      const p = run("serve", "--help");
      expect(p.stdout).toContain("--out");
      expect(p.stdout).toContain("--port");
    });
  });

  describe("dev command", () => {
    it("accepts full set of options", () => {
      const p = run("dev", "--help");
      expect(p.stdout).toContain("--src");
      expect(p.stdout).toContain("--tmpl");
      expect(p.stdout).toContain("--out");
      expect(p.stdout).toContain("--port");
    });
  });

  describe("help output", () => {
    it("shows available commands", () => {
      const p = run("--help");
      expect(p.stdout).toContain("build");
      expect(p.stdout).toContain("dev");
      expect(p.stdout).toContain("serve");
    });
  });
});
