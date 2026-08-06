import { describe, it, expect } from "vitest";
import { parseArgs, printHelp } from "../src/cli";

describe("parseArgs", () => {
  it("returns defaults when no args provided", () => {
    const config = parseArgs([]);
    expect(config.sourceDir).toBe("./content");
    expect(config.templateDir).toBe("./templates");
    expect(config.outputDir).toBe("./dist");
    expect(config.port).toBe(3000);
    expect(config.siteTitle).toBe("My Static Site");
    expect(config.siteUrl).toBe("http://localhost:3000");
    expect(config.serve).toBe(false);
    expect(config.watch).toBe(false);
  });

  it("parses -s / --source flag", () => {
    expect(parseArgs(["-s", "mycontent"]).sourceDir).toBe("mycontent");
    expect(parseArgs(["--source", "blog"]).sourceDir).toBe("blog");
  });

  it("parses -t / --templates flag", () => {
    expect(parseArgs(["-t", "mytemplates"]).templateDir).toBe("mytemplates");
    expect(parseArgs(["--templates", "theme"]).templateDir).toBe("theme");
  });

  it("parses -o / --output flag", () => {
    expect(parseArgs(["-o", "public"]).outputDir).toBe("public");
    expect(parseArgs(["--output", "www"]).outputDir).toBe("www");
  });

  it("parses -p / --port flag", () => {
    expect(parseArgs(["-p", "8080"]).port).toBe(8080);
    expect(parseArgs(["--port", "9000"]).port).toBe(9000);
  });

  it("parses --title flag", () => {
    expect(parseArgs(["--title", "My Blog"]).siteTitle).toBe("My Blog");
  });

  it("parses --url flag", () => {
    expect(parseArgs(["--url", "https://example.com"]).siteUrl).toBe("https://example.com");
  });

  it("parses -S / --serve flag", () => {
    expect(parseArgs(["-S"]).serve).toBe(true);
    expect(parseArgs(["--serve"]).serve).toBe(true);
  });

  it("parses -w / --watch flag", () => {
    expect(parseArgs(["-w"]).watch).toBe(true);
    expect(parseArgs(["--watch"]).watch).toBe(true);
  });

  it("combines multiple flags", () => {
    const config = parseArgs(["-s", "src", "-o", "out", "--serve", "--title", "My Cool Site"]);
    expect(config.sourceDir).toBe("src");
    expect(config.outputDir).toBe("out");
    expect(config.serve).toBe(true);
    expect(config.siteTitle).toBe("My Cool Site");
  });

  it("skips flag value if next arg is also a flag", () => {
    const config = parseArgs(["-s", "-o", "out"]);
    expect(config.sourceDir).toBe("./content");
    expect(config.outputDir).toBe("out");
  });
});

describe("printHelp", () => {
  it("contains usage information", () => {
    const help = printHelp();
    expect(help).toContain("statico");
    expect(help).toContain("--source");
    expect(help).toContain("--templates");
    expect(help).toContain("--output");
    expect(help).toContain("--serve");
    expect(help).toContain("--help");
  });
});
