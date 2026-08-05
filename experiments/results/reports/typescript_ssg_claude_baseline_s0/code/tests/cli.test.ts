import { describe, it, expect } from "vitest";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import path from "node:path";
import { parseCliArgs, HELP } from "../src/cli.js";
import { makeFixture, exists, readOut } from "./helpers.js";

const execFileAsync = promisify(execFile);
const ROOT = path.resolve(__dirname, "..");
const TSX = path.join(ROOT, "node_modules", ".bin", "tsx");
const CLI = path.join(ROOT, "src", "cli.ts");

function runCli(args: string[], cwd = ROOT) {
  return execFileAsync(TSX, [CLI, ...args], { cwd });
}

describe("parseCliArgs", () => {
  it("defaults to the build command with default options", () => {
    const cli = parseCliArgs([]);
    expect(cli.command).toBe("build");
    expect(cli.options.sourceDir).toBe(path.resolve("content"));
    expect(cli.options.templateDir).toBe(path.resolve("templates"));
    expect(cli.options.outDir).toBe(path.resolve("dist-site"));
    expect(cli.options.port).toBe(4000);
    expect(cli.options.includeDrafts).toBe(false);
  });

  it("parses long and short flags", () => {
    const cli = parseCliArgs([
      "serve",
      "-s", "src-content",
      "-t", "tpl",
      "-o", "public",
      "-p", "8080",
      "--drafts",
      "--base-url", "https://blog.example",
      "--title", "My Blog",
    ]);
    expect(cli.command).toBe("serve");
    expect(cli.options.sourceDir).toBe(path.resolve("src-content"));
    expect(cli.options.templateDir).toBe(path.resolve("tpl"));
    expect(cli.options.outDir).toBe(path.resolve("public"));
    expect(cli.options.port).toBe(8080);
    expect(cli.options.includeDrafts).toBe(true);
    expect(cli.options.site?.baseUrl).toBe("https://blog.example");
    expect(cli.options.site?.title).toBe("My Blog");
  });

  it("recognizes help and version flags", () => {
    expect(parseCliArgs(["-h"]).command).toBe("help");
    expect(parseCliArgs(["--version"]).command).toBe("version");
    expect(HELP).toContain("statik build");
  });

  it("rejects unknown commands and invalid ports", () => {
    expect(() => parseCliArgs(["frobnicate"])).toThrow(/Unknown command/);
    expect(() => parseCliArgs(["build", "-p", "notaport"])).toThrow(/Invalid port/);
    expect(() => parseCliArgs(["build", "-p", "99999"])).toThrow(/Invalid port/);
    expect(() => parseCliArgs(["--bogus-flag"])).toThrow();
  });
});

describe("CLI end-to-end", () => {
  it("builds a site via `statik build` and reports a summary", async () => {
    const fixture = await makeFixture();
    try {
      const { stdout } = await runCli([
        "build",
        "-s", fixture.sourceDir,
        "-t", fixture.templateDir,
        "-o", fixture.outDir,
        "--title", "E2E Site",
        "--base-url", "https://e2e.example",
      ]);
      expect(stdout).toMatch(/Built 3 page\(s\), 3 tag page\(s\), skipped 1 draft\(s\)/);
      expect(await exists(fixture, "posts/hello/index.html")).toBe(true);
      expect(await exists(fixture, "posts/secret/index.html")).toBe(false);
      expect(await readOut(fixture, "feed.xml")).toContain("https://e2e.example/posts/hello/");
    } finally {
      await fixture.cleanup();
    }
  }, 30000);

  it("includes drafts with --drafts", async () => {
    const fixture = await makeFixture();
    try {
      const { stdout } = await runCli([
        "build",
        "-s", fixture.sourceDir,
        "-t", fixture.templateDir,
        "-o", fixture.outDir,
        "--drafts",
      ]);
      expect(stdout).toMatch(/Built 4 page\(s\)/);
      expect(await exists(fixture, "posts/secret/index.html")).toBe(true);
    } finally {
      await fixture.cleanup();
    }
  }, 30000);

  it("prints help with --help and exits 0", async () => {
    const { stdout } = await runCli(["--help"]);
    expect(stdout).toContain("Usage:");
    expect(stdout).toContain("--drafts");
  }, 30000);

  it("exits non-zero on an unknown command", async () => {
    await expect(runCli(["explode"])).rejects.toMatchObject({ code: 1 });
  }, 30000);
});
