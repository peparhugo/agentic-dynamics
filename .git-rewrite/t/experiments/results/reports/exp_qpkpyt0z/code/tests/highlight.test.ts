import { describe, it, expect, afterAll } from "vitest";
import { rm } from "node:fs/promises";
import { generate } from "../src/generator.js";
import { markdownToHtml } from "../src/highlight.js";
import { makeConfig } from "./helpers.js";
import { readFile, access } from "node:fs/promises";
import { join } from "node:path";

describe("syntax highlighting", () => {
  afterAll(async () => {
    await rm(makeConfig().outputDir, { recursive: true, force: true });
  });

  it("adds highlight.js classes to code blocks", () => {
    const md = "```javascript\nconst x = 1;\n```";
    const html = markdownToHtml(md);
    expect(html).toContain("hljs");
    expect(html).toContain("javascript");
    expect(html).toContain("const x = 1");
  });

  it("handles auto-detection for unknown languages", () => {
    const md = "```\nconst x = 1;\n```";
    const html = markdownToHtml(md);
    expect(html).toContain("hljs");
  });

  it("renders highlighted code in generated pages", async () => {
    const config = makeConfig();
    await generate(config);

    const html = await readFile(join(config.outputDir, "posts/hello-world/index.html"), "utf-8");
    expect(html).toContain("hljs");
    expect(html).toContain("hello world");
  });
});
