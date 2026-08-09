import { describe, it, expect, afterAll } from "vitest";
import { spawnSync } from "node:child_process";
import path from "node:path";
import fs from "node:fs/promises";
import os from "node:os";

async function setupCliTest() {
  const baseDir = await fs.mkdtemp(path.join(os.tmpdir(), "ssg-cli-"));
  const srcDir = path.join(baseDir, "content");
  const tmplDir = path.join(baseDir, "templates");
  const outDir = path.join(baseDir, "output");

  await fs.mkdir(srcDir, { recursive: true });
  await fs.mkdir(tmplDir, { recursive: true });

  await fs.writeFile(
    path.join(tmplDir, "layout.hbs"),
    `<html><body><h1>{{title}}</h1>{{{content}}}</body></html>`,
  );

  await fs.writeFile(
    path.join(srcDir, "test.md"),
    `---
title: CLI Test
date: 2024-01-01
---
# CLI Post`,
  );

  const cliPath = path.resolve("dist/cli.js");

  return { baseDir, srcDir, tmplDir, outDir, cliPath };
}

function runCli(args: string): string {
  const result = spawnSync("node", ["dist/cli.js", ...args.split(/\s+/)], {
    encoding: "utf-8",
  });
  return result.stdout + result.stderr;
}

describe("CLI", { timeout: 30000 }, () => {
  let dirs: Awaited<ReturnType<typeof setupCliTest>>;

  afterAll(async () => {
    if (dirs) {
      await fs.rm(dirs.baseDir, { recursive: true, force: true });
    }
  });

  it("builds site with required options", async () => {
    dirs = await setupCliTest();

    const args = [
      `--source "${dirs.srcDir}"`,
      `--templates "${dirs.tmplDir}"`,
      `--output "${dirs.outDir}"`,
    ].join(" ");

    runCli(args);

    const output = await fs.readFile(
      path.join(dirs.outDir, "test.html"),
      "utf-8",
    );
    expect(output).toContain("CLI Test");
    expect(output).toContain("CLI Post");
  });

  it("shows help with --help", () => {
    const result = runCli("--help");
    expect(result).toContain("Usage:");
    expect(result).toContain("--source");
    expect(result).toContain("--templates");
    expect(result).toContain("--output");
  });

  it("shows version", () => {
    const result = runCli("--version");
    expect(result).toContain("1.0.0");
  });

  it("accepts --title and --base-url options", async () => {
    dirs = await setupCliTest();

    const args = [
      `--source "${dirs.srcDir}"`,
      `--templates "${dirs.tmplDir}"`,
      `--output "${dirs.outDir}"`,
      `--title "Custom Title"`,
      `--base-url "https://example.org"`,
    ].join(" ");

    runCli(args);

    const rssContent = await fs.readFile(
      path.join(dirs.outDir, "rss.xml"),
      "utf-8",
    );
    expect(rssContent).toContain("Custom Title");
    expect(rssContent).toContain("https://example.org");
  });

  it("errors when missing required options", () => {
    const result = runCli("--source ./src");
    expect(result).toContain("required option");
  });
});
