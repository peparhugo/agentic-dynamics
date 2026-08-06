import { describe, it, expect, afterEach, vi } from "vitest";
import { promises as fs } from "node:fs";
import path from "node:path";
import { parseArgs, main, CliError } from "../src/cli.js";
import { makeFixture, type Fixture, DEFAULT_LAYOUT } from "./helpers.js";

let fixture: Fixture | null = null;
afterEach(async () => {
  await fixture?.cleanup();
  fixture = null;
  vi.restoreAllMocks();
});

describe("parseArgs", () => {
  it("parses build with defaults", () => {
    const opts = parseArgs(["build"]);
    expect(opts.command).toBe("build");
    expect(opts.config.sourceDir).toBe(path.resolve("content"));
    expect(opts.config.templateDir).toBe(path.resolve("templates"));
    expect(opts.config.outputDir).toBe(path.resolve("dist-site"));
    expect(opts.config.includeDrafts).toBe(false);
    expect(opts.port).toBe(3000);
  });

  it("parses long and short flags", () => {
    const opts = parseArgs([
      "serve",
      "-s", "src-md",
      "--templates", "tpl",
      "-o", "out",
      "--port", "8080",
      "--drafts",
      "--site-title", "Blog",
      "--site-url", "https://blog.example",
    ]);
    expect(opts.command).toBe("serve");
    expect(opts.config.sourceDir).toBe(path.resolve("src-md"));
    expect(opts.config.templateDir).toBe(path.resolve("tpl"));
    expect(opts.config.outputDir).toBe(path.resolve("out"));
    expect(opts.port).toBe(8080);
    expect(opts.config.includeDrafts).toBe(true);
    expect(opts.config.siteTitle).toBe("Blog");
    expect(opts.config.siteUrl).toBe("https://blog.example");
  });

  it("rejects missing command", () => {
    expect(() => parseArgs([])).toThrow(CliError);
    expect(() => parseArgs(["--drafts"])).toThrow(/Missing command/);
  });

  it("rejects unknown flags", () => {
    expect(() => parseArgs(["build", "--bogus"])).toThrow(/Unknown argument/);
  });

  it("rejects flags missing values", () => {
    expect(() => parseArgs(["build", "--source"])).toThrow(/Missing value/);
    expect(() => parseArgs(["build", "-o", "--drafts"])).toThrow(/Missing value/);
  });

  it("rejects invalid ports", () => {
    expect(() => parseArgs(["serve", "-p", "abc"])).toThrow(/Invalid port/);
    expect(() => parseArgs(["serve", "-p", "70000"])).toThrow(/Invalid port/);
  });

  it("treats --help as its own command", () => {
    expect(parseArgs(["--help"]).command).toBe("help");
    expect(parseArgs(["build", "-h"]).command).toBe("help");
  });
});

describe("main", () => {
  it("builds a site end-to-end and reports a summary", async () => {
    fixture = await makeFixture({
      "templates/layouts/default.hbs": DEFAULT_LAYOUT,
      "templates/partials/nav.hbs": "<nav/>",
      "content/hello.md": `---\ntitle: Hello\ndate: 2024-01-01\ntags: [x]\n---\n# Hi\n`,
      "content/draft.md": `---\ntitle: Secret\ndraft: true\n---\nshh`,
    });
    const log = vi.spyOn(console, "log").mockImplementation(() => {});
    const code = await main([
      "build",
      "-s", fixture.sourceDir,
      "-t", fixture.templateDir,
      "-o", fixture.outputDir,
    ]);
    expect(code).toBe(0);
    expect(log).toHaveBeenCalledWith(expect.stringMatching(/Built 1 page\(s\), 1 tag page\(s\).*skipped 1 draft/));
    await fs.access(path.join(fixture.outputDir, "hello.html"));
    await fs.access(path.join(fixture.outputDir, "feed.xml"));
    await expect(fs.access(path.join(fixture.outputDir, "draft.html"))).rejects.toThrow();
  });

  it("includes drafts with --drafts", async () => {
    fixture = await makeFixture({
      "templates/layouts/default.hbs": DEFAULT_LAYOUT,
      "templates/partials/nav.hbs": "",
      "content/draft.md": `---\ntitle: Secret\ndraft: true\n---\nshh`,
    });
    vi.spyOn(console, "log").mockImplementation(() => {});
    const code = await main([
      "build", "--drafts",
      "-s", fixture.sourceDir,
      "-t", fixture.templateDir,
      "-o", fixture.outputDir,
    ]);
    expect(code).toBe(0);
    await fs.access(path.join(fixture.outputDir, "draft.html"));
  });

  it("returns exit code 2 and prints usage on bad flags", async () => {
    const err = vi.spyOn(console, "error").mockImplementation(() => {});
    const code = await main(["build", "--nope"]);
    expect(code).toBe(2);
    expect(err).toHaveBeenCalledWith(expect.stringContaining("Unknown argument: --nope"));
    expect(err).toHaveBeenCalledWith(expect.stringContaining("Usage:"));
  });

  it("prints help with --help and exits 0", async () => {
    const log = vi.spyOn(console, "log").mockImplementation(() => {});
    const code = await main(["--help"]);
    expect(code).toBe(0);
    expect(log).toHaveBeenCalledWith(expect.stringContaining("ssg - static site generator"));
  });
});
