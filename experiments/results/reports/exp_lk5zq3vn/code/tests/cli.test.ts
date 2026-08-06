import { describe, it, expect } from "vitest";
import { parseArgs } from "../src/cli.js";

describe("parseArgs", () => {
  it("defaults to help with no args", () => {
    expect(parseArgs([]).command).toBe("help");
  });

  it("parses build with defaults", () => {
    const o = parseArgs(["build"]);
    expect(o.command).toBe("build");
    expect(o.config.sourceDir).toBe("content");
    expect(o.config.templateDir).toBe("templates");
    expect(o.config.outDir).toBe("dist-site");
    expect(o.config.includeDrafts).toBe(false);
  });

  it("parses long and short flags", () => {
    const o = parseArgs([
      "build", "-s", "src-md", "--templates", "tpl", "-o", "out",
      "--drafts", "--base-url", "https://example.com", "--title", "T", "--description", "D",
    ]);
    expect(o.config).toMatchObject({
      sourceDir: "src-md",
      templateDir: "tpl",
      outDir: "out",
      includeDrafts: true,
      baseUrl: "https://example.com",
      siteTitle: "T",
      siteDescription: "D",
    });
  });

  it("parses serve with port", () => {
    const o = parseArgs(["serve", "-p", "8080"]);
    expect(o.command).toBe("serve");
    expect(o.port).toBe(8080);
  });

  it("rejects invalid port", () => {
    expect(() => parseArgs(["serve", "--port", "99999"])).toThrow(/Invalid port/);
    expect(() => parseArgs(["serve", "--port", "abc"])).toThrow(/Invalid port/);
  });

  it("rejects unknown commands and flags", () => {
    expect(() => parseArgs(["deploy"])).toThrow(/Unknown command/);
    expect(() => parseArgs(["build", "--wat"])).toThrow(/Unknown flag/);
  });

  it("rejects flags missing values", () => {
    expect(() => parseArgs(["build", "--source"])).toThrow(/Missing value/);
    expect(() => parseArgs(["build", "-s", "--drafts"])).toThrow(/Missing value/);
  });

  it("treats -h/--help anywhere as help", () => {
    expect(parseArgs(["--help"]).command).toBe("help");
    expect(parseArgs(["build", "-h"]).command).toBe("help");
  });
});
