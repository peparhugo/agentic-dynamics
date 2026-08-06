import { describe, it, expect } from "vitest";
import { parseArgs } from "../src/cli/main";

describe("CLI parseArgs", () => {
  it("defaults to build command with default paths", () => {
    const args = parseArgs([]);
    expect(args.command).toBe("build");
    expect(args.source).toBe("content");
    expect(args.templates).toBe("templates");
    expect(args.output).toBe("dist");
    expect(args.port).toBe(3000);
  });

  it("sets command to serve", () => {
    const args = parseArgs(["serve"]);
    expect(args.command).toBe("serve");
  });

  it("sets build command explicitly", () => {
    const args = parseArgs(["build"]);
    expect(args.command).toBe("build");
  });

  it("parses --source flag (short)", () => {
    const args = parseArgs(["-s", "mycontent"]);
    expect(args.source).toBe("mycontent");
  });

  it("parses --source flag (long)", () => {
    const args = parseArgs(["--source", "mycontent"]);
    expect(args.source).toBe("mycontent");
  });

  it("parses --templates flag", () => {
    const args = parseArgs(["-t", "mytemplates"]);
    expect(args.templates).toBe("mytemplates");
  });

  it("parses --output flag", () => {
    const args = parseArgs(["-o", "public"]);
    expect(args.output).toBe("public");
  });

  it("parses --port flag", () => {
    const args = parseArgs(["-p", "8080"]);
    expect(args.port).toBe(8080);
  });

  it("parses combined flags", () => {
    const args = parseArgs(["serve", "-s", "src", "-t", "tpl", "-o", "out", "-p", "4000"]);
    expect(args.command).toBe("serve");
    expect(args.source).toBe("src");
    expect(args.templates).toBe("tpl");
    expect(args.output).toBe("out");
    expect(args.port).toBe(4000);
  });

  it("gracefully handles missing value after flag", () => {
    const args = parseArgs(["-s"]);
    expect(args.source).toBe("content"); // keeps default
  });

  it("treats unexpected tokens as build command (defaults)", () => {
    const args = parseArgs(["something"]);
    expect(args.command).toBe("build");
  });
});
