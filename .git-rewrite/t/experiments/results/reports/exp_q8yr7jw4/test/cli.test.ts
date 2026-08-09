import { describe, it, expect } from "vitest";
import path from "node:path";
import { parseArgs, toSiteConfig, DEFAULTS } from "../src/cli.js";

describe("parseArgs", () => {
  it("defaults to help with no args", () => {
    expect(parseArgs([]).command).toBe("help");
    expect(parseArgs(["--help"]).command).toBe("help");
    expect(parseArgs(["-h"]).command).toBe("help");
  });

  it("parses the build command with defaults", () => {
    const opts = parseArgs(["build"]);
    expect(opts.command).toBe("build");
    expect(opts.source).toBe(DEFAULTS.source);
    expect(opts.templates).toBe(DEFAULTS.templates);
    expect(opts.out).toBe(DEFAULTS.out);
    expect(opts.drafts).toBe(false);
    expect(opts.port).toBe(DEFAULTS.port);
  });

  it("parses long flags", () => {
    const opts = parseArgs([
      "build",
      "--source", "src-md",
      "--templates", "tpl",
      "--out", "public",
      "--base-url", "https://blog.test",
      "--title", "Blog",
      "--drafts",
    ]);
    expect(opts.source).toBe("src-md");
    expect(opts.templates).toBe("tpl");
    expect(opts.out).toBe("public");
    expect(opts.baseUrl).toBe("https://blog.test");
    expect(opts.title).toBe("Blog");
    expect(opts.drafts).toBe(true);
  });

  it("parses short aliases", () => {
    const opts = parseArgs(["serve", "-s", "a", "-t", "b", "-o", "c", "-p", "8080"]);
    expect(opts.command).toBe("serve");
    expect(opts.source).toBe("a");
    expect(opts.templates).toBe("b");
    expect(opts.out).toBe("c");
    expect(opts.port).toBe(8080);
  });

  it("rejects unknown commands and flags", () => {
    expect(() => parseArgs(["frobnicate"])).toThrow(/Unknown command/);
    expect(() => parseArgs(["build", "--wat"])).toThrow(/Unknown flag/);
  });

  it("rejects missing flag values", () => {
    expect(() => parseArgs(["build", "--source"])).toThrow(/Missing value/);
    expect(() => parseArgs(["build", "--source", "--drafts"])).toThrow(/Missing value/);
  });

  it("validates port numbers", () => {
    expect(() => parseArgs(["serve", "--port", "abc"])).toThrow(/Invalid port/);
    expect(() => parseArgs(["serve", "--port", "70000"])).toThrow(/Invalid port/);
    expect(parseArgs(["serve", "--port", "0"]).port).toBe(0);
  });
});

describe("toSiteConfig", () => {
  it("resolves directories against cwd and maps options", () => {
    const opts = parseArgs(["build", "-s", "md", "-o", "out", "--drafts", "--title", "T", "--base-url", "https://x.test"]);
    const site = toSiteConfig(opts, "/work");
    expect(site.sourceDir).toBe(path.resolve("/work", "md"));
    expect(site.outDir).toBe(path.resolve("/work", "out"));
    expect(site.templateDir).toBe(path.resolve("/work", "templates"));
    expect(site.includeDrafts).toBe(true);
    expect(site.title).toBe("T");
    expect(site.baseUrl).toBe("https://x.test");
  });
});
