import { describe, it, expect, afterEach } from "vitest";
import { readFile, rm } from "node:fs/promises";
import { join } from "node:path";
import { build } from "../src/build.js";
import type { SiteConfig } from "../src/types.js";

const outputDir = join(__dirname, "fixtures", "output");
const sourceDir = join(__dirname, "fixtures", "posts");
const templateDir = join(__dirname, "fixtures", "templates");

const config: SiteConfig = {
  sourceDir,
  templateDir,
  outputDir,
  siteTitle: "Test Site",
  siteUrl: "http://localhost:3000",
};

afterEach(async () => {
  await rm(outputDir, { recursive: true, force: true });
});

describe("CLI build", () => {
  it("builds HTML pages from markdown files", async () => {
    const result = await build(config);
    expect(result.errors).toEqual([]);
    expect(result.pages.length).toBe(3);

    const helloHtml = await readFile(
      join(outputDir, "hello", "index.html"),
      "utf-8"
    );
    expect(helloHtml).toContain("Hello World");
    expect(helloHtml).toContain('class="hljs');
    expect(helloHtml).toContain("console");
  });

  it("skips draft posts", async () => {
    const result = await build(config);
    const draftExists = await fileExists(
      join(outputDir, "draft", "index.html")
    );
    expect(draftExists).toBe(false);

    const indexHtml = await readFile(
      join(outputDir, "index.html"),
      "utf-8"
    );
    expect(indexHtml).not.toContain("Secret Draft");
    expect(indexHtml).toContain("Hello World");
  });

  it("generates tag index pages", async () => {
    await build(config);

    const tutorialHtml = await readFile(
      join(outputDir, "tags", "tutorial", "index.html"),
      "utf-8"
    );
    expect(tutorialHtml).toContain("Tag: tutorial");
    expect(tutorialHtml).toContain("Hello World");
    expect(tutorialHtml).toContain("Second Post");

    const jsHtml = await readFile(
      join(outputDir, "tags", "javascript", "index.html"),
      "utf-8"
    );
    expect(jsHtml).toContain("Tag: javascript");
    expect(jsHtml).toContain("Hello World");
  });

  it("generates RSS feed", async () => {
    await build(config);

    const rss = await readFile(join(outputDir, "feed.xml"), "utf-8");
    expect(rss).toContain("<rss version=\"2.0\"");
    expect(rss).toContain("<title>Test Site</title>");
    expect(rss).toContain("<title>Hello World</title>");
    expect(rss).toContain("<title>Second Post</title>");
    expect(rss).not.toContain("Secret Draft");
  });

  it("uses layout template with partials", async () => {
    await build(config);

    const helloHtml = await readFile(
      join(outputDir, "hello", "index.html"),
      "utf-8"
    );
    expect(helloHtml).toContain("<!DOCTYPE html>");
    expect(helloHtml).toContain("<nav>My Site Navigation</nav>");
    expect(helloHtml).toContain("<time>2024-01-15</time>");
  });
});

async function fileExists(path: string): Promise<boolean> {
  try {
    await readFile(path);
    return true;
  } catch {
    return false;
  }
}
