import { describe, it, expect, afterAll } from "vitest";
import { rm } from "node:fs/promises";
import { generate } from "../src/generator.js";
import { makeConfig } from "./helpers.js";
import { access, readFile } from "node:fs/promises";
import { join } from "node:path";

describe("generate", () => {
  afterAll(async () => {
    await rm(makeConfig().outputDir, { recursive: true, force: true });
  });

  it("generates HTML files from Markdown", async () => {
    const config = makeConfig();
    await generate(config);

    await expect(access(join(config.outputDir, "posts/hello-world/index.html"))).resolves.toBeUndefined();

    const html = await readFile(join(config.outputDir, "posts/hello-world/index.html"), "utf-8");
    expect(html).toContain("Hello World");
    expect(html).toContain("<h1>");
  });

  it("skips draft posts", async () => {
    const config = makeConfig();
    await generate(config);

    await expect(
      access(join(config.outputDir, "posts/draft-post/index.html"))
    ).rejects.toThrow();
  });

  it("generates index page", async () => {
    const config = makeConfig();
    await generate(config);

    const html = await readFile(join(config.outputDir, "index.html"), "utf-8");
    expect(html).toContain("Test Site");
    expect(html).toContain("Hello World");
    expect(html).toContain("Second Post");
    expect(html).not.toContain("Draft Post");
  });

  it("generates RSS feed", async () => {
    const config = makeConfig();
    await generate(config);

    const rss = await readFile(join(config.outputDir, "rss.xml"), "utf-8");
    expect(rss).toContain("<?xml");
    expect(rss).toContain("Hello World");
    expect(rss).not.toContain("Draft Post");
  });

  it("generates tag index pages", async () => {
    const config = makeConfig();
    await generate(config);

    const tagHtml = await readFile(join(config.outputDir, "tags/backend/index.html"), "utf-8");
    expect(tagHtml).toContain("backend");
    expect(tagHtml).toContain("Second Post");
  });

  it("does not generate tag index entries for drafts", async () => {
    const config = makeConfig();
    await generate(config);

    await expect(
      access(join(config.outputDir, "tags/drafting/index.html"))
    ).rejects.toThrow();
  });
});
