import { describe, it, expect, beforeAll, afterAll } from "vitest";
import { mkdtempSync, rmSync, readFileSync, existsSync } from "node:fs";
import { resolve, join } from "node:path";
import { generate } from "../src/generator.js";
import type { SiteConfig } from "../src/types.js";

const tmpDirs: string[] = [];

function tmpDir(): string {
  const d = mkdtempSync("/tmp/ssg-test-");
  tmpDirs.push(d);
  return d;
}

afterAll(() => {
  for (const d of tmpDirs) {
    rmSync(d, { recursive: true, force: true });
  }
});

describe("generate", () => {
  it("generates HTML files for each markdown post", async () => {
    const out = tmpDir();
    const config: SiteConfig = {
      src: resolve("tests/fixtures/content"),
      tmpl: resolve("tests/fixtures/templates"),
      out,
      port: 3000,
      baseUrl: "http://localhost:3000",
      title: "TestSite",
      description: "Test site",
    };
    await generate(config);

    expect(existsSync(join(out, "hello.html"))).toBe(true);
    expect(existsSync(join(out, "tagged-post.html"))).toBe(true);
    expect(existsSync(join(out, "index.html"))).toBe(true);
  });

  it("skips draft posts", async () => {
    const out = tmpDir();
    const config: SiteConfig = {
      src: resolve("tests/fixtures/content"),
      tmpl: resolve("tests/fixtures/templates"),
      out,
      port: 3000,
      baseUrl: "http://localhost:3000",
      title: "TestSite",
      description: "Test site",
    };
    await generate(config);

    expect(existsSync(join(out, "draft-post.html"))).toBe(false);
  });

  it("generates tag index pages", async () => {
    const out = tmpDir();
    const config: SiteConfig = {
      src: resolve("tests/fixtures/content"),
      tmpl: resolve("tests/fixtures/templates"),
      out,
      port: 3000,
      baseUrl: "http://localhost:3000",
      title: "TestSite",
      description: "Test site",
    };
    await generate(config);

    expect(existsSync(join(out, "tags", "example.html"))).toBe(true);
    expect(existsSync(join(out, "tags", "test.html"))).toBe(true);
    expect(existsSync(join(out, "tags", "another.html"))).toBe(true);
  });

  it("generates RSS feed", async () => {
    const out = tmpDir();
    const config: SiteConfig = {
      src: resolve("tests/fixtures/content"),
      tmpl: resolve("tests/fixtures/templates"),
      out,
      port: 3000,
      baseUrl: "http://localhost:3000",
      title: "TestSite",
      description: "Test site",
    };
    await generate(config);

    const rss = readFileSync(join(out, "rss.xml"), "utf-8");
    expect(rss).toContain("<rss");
    expect(rss).toContain("<channel>");
    expect(rss).toContain("<title>TestSite</title>");
    expect(rss).toContain("<item>");
    expect(rss).toContain("Hello World");
    expect(rss).not.toContain("Draft Post");
  });

  it("renders syntax highlighted code blocks in output", async () => {
    const out = tmpDir();
    const config: SiteConfig = {
      src: resolve("tests/fixtures/content"),
      tmpl: resolve("tests/fixtures/templates"),
      out,
      port: 3000,
      baseUrl: "http://localhost:3000",
      title: "TestSite",
      description: "Test site",
    };
    await generate(config);

    const html = readFileSync(join(out, "hello.html"), "utf-8");
    expect(html).toContain("hljs");
    expect(html).toContain("language-js");
  });

  it("post HTML includes title and tags", async () => {
    const out = tmpDir();
    const config: SiteConfig = {
      src: resolve("tests/fixtures/content"),
      tmpl: resolve("tests/fixtures/templates"),
      out,
      port: 3000,
      baseUrl: "http://localhost:3000",
      title: "TestSite",
      description: "Test site",
    };
    await generate(config);

    const html = readFileSync(join(out, "hello.html"), "utf-8");
    expect(html).toContain("Hello World");
    expect(html).toContain("example");
    expect(html).toContain("test");
  });

  it("tag page lists correct posts", async () => {
    const out = tmpDir();
    const config: SiteConfig = {
      src: resolve("tests/fixtures/content"),
      tmpl: resolve("tests/fixtures/templates"),
      out,
      port: 3000,
      baseUrl: "http://localhost:3000",
      title: "TestSite",
      description: "Test site",
    };
    await generate(config);

    const tagPage = readFileSync(join(out, "tags", "example.html"), "utf-8");
    expect(tagPage).toContain("Hello World");
    expect(tagPage).toContain("Tagged Post");
  });
});
