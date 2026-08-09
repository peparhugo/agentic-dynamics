import { describe, it, before, after } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, existsSync, rmSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { build } from "../src/build.js";
import { generateRss } from "../src/rss.js";

const __dirname = fileURLToPath(new URL(".", import.meta.url));
const fixtures = join(__dirname, "fixtures");
const outDir = join(__dirname, "fixtures/_output");

describe("build", () => {
  before(() => {
    if (existsSync(outDir)) rmSync(outDir, { recursive: true });
  });

  after(() => {
    if (existsSync(outDir)) rmSync(outDir, { recursive: true });
  });

  it("generates index.html with posts sorted by date descending", () => {
    const result = build({
      sourceDir: join(fixtures, "content"),
      templateDir: join(fixtures, "templates"),
      outputDir: outDir,
      baseUrl: "http://localhost:3000/",
      siteTitle: "Test Site",
      siteDescription: "A test site",
    });

    assert.ok(existsSync(join(outDir, "index.html")));
    const html = readFileSync(join(outDir, "index.html"), "utf-8");
    // Second post (feb) should come before hello-world (jan)
    const secondIdx = html.indexOf("Second Post");
    const helloIdx = html.indexOf("Hello World");
    assert.ok(secondIdx < helloIdx, "posts sorted by date descending");
    assert.ok(html.includes("Test Site"));
    assert.ok(html.includes("<footer>"), "partial footer is included");
  });

  it("generates individual post pages", () => {
    assert.ok(existsSync(join(outDir, "hello-world", "index.html")));
    assert.ok(existsSync(join(outDir, "second-post", "index.html")));

    const postHtml = readFileSync(join(outDir, "hello-world", "index.html"), "utf-8");
    assert.ok(postHtml.includes("Hello World"), "post title in output");
    assert.ok(postHtml.includes("2025-01-15"), "post date in output");
    assert.ok(postHtml.includes("intro"), "tag in output");
    assert.ok(postHtml.includes("meta"), "tag in output");
    assert.ok(postHtml.includes("<h1>Hello World</h1>"), "markdown rendered as HTML");
  });

  it("filters out draft posts", () => {
    assert.equal(existsSync(join(outDir, "draft-post", "index.html")), false);
    const indexPath = join(outDir, "index.html");
    const indexHtml = readFileSync(indexPath, "utf-8");
    assert.ok(!indexHtml.includes("draft-post"), "draft not in index");
  });

  it("generates tag index pages", () => {
    assert.ok(existsSync(join(outDir, "tags", "tech", "index.html")));
    assert.ok(existsSync(join(outDir, "tags", "js", "index.html")));
    assert.ok(existsSync(join(outDir, "tags", "meta", "index.html")));

    const tagHtml = readFileSync(join(outDir, "tags", "tech", "index.html"), "utf-8");
    assert.ok(tagHtml.includes("tech"), "tag name in output");
  });

  it("does not generate tag pages for draft-only tags", () => {
    assert.equal(existsSync(join(outDir, "tags", "draft-tag", "index.html")), false);
  });

  it("returns post and tag page counts", () => {
    const result = build({
      sourceDir: join(fixtures, "content"),
      templateDir: join(fixtures, "templates"),
      outputDir: outDir,
      baseUrl: "http://localhost:3000/",
      siteTitle: "Test Site",
      siteDescription: "A test site",
    });
    assert.equal(result.posts.length, 2, "2 non-draft posts");
    assert.ok(result.tagPages.length >= 4, "at least 4 unique tags");
  });

  it("renders syntax highlighted code blocks in posts", () => {
    const postHtml = readFileSync(join(outDir, "second-post", "index.html"), "utf-8");
    assert.ok(postHtml.includes("hljs"), "syntax highlighting classes present");
  });

  it("includes inline code in output", () => {
    const postHtml = readFileSync(join(outDir, "second-post", "index.html"), "utf-8");
    assert.ok(postHtml.includes("inline code"), "inline code preserved");
  });
});

describe("rss", () => {
  after(() => {
    if (existsSync(outDir)) rmSync(outDir, { recursive: true });
  });

  it("generates valid RSS XML", () => {
    const result = build({
      sourceDir: join(fixtures, "content"),
      templateDir: join(fixtures, "templates"),
      outputDir: outDir,
      baseUrl: "http://example.com/",
      siteTitle: "RSS Test",
      siteDescription: "Testing RSS feed generation",
    });

    generateRss(result.posts, outDir, "http://example.com/", "RSS Test", "Testing RSS feed generation");

    const rss = readFileSync(join(outDir, "rss.xml"), "utf-8");
    assert.ok(rss.includes('<?xml version="1.0" encoding="UTF-8"?>'));
    assert.ok(rss.includes("<rss version=\"2.0\""));
    assert.ok(rss.includes("<title>RSS Test</title>"));
    assert.ok(rss.includes("<link>http://example.com/</link>"));
    assert.ok(rss.includes("<title><![CDATA[Hello World]]></title>"));
    assert.ok(rss.includes("<title><![CDATA[Second Post]]></title>"));
    assert.ok(rss.includes("<guid>http://example.com/hello-world/</guid>"));
  });

  it("only includes dated posts in RSS", () => {
    const posts = [
      { title: "No date", tags: [], draft: false, content: "", slug: "no-date", raw: "" },
      { title: "Has date", date: new Date("2025-01-01"), tags: [], draft: false, content: "", slug: "has-date", raw: "" },
    ];

    const out = join(outDir, "rss");
    build({
      sourceDir: join(fixtures, "content"),
      templateDir: join(fixtures, "templates"),
      outputDir: out,
      baseUrl: "http://example.com/",
      siteTitle: "T",
      siteDescription: "D",
    });
    generateRss(posts, out, "http://example.com/", "T", "D");

    const rss = readFileSync(join(out, "rss.xml"), "utf-8");
    assert.ok(rss.includes("Has date"));
    assert.ok(!rss.includes("No date"));
    rmSync(out, { recursive: true });
  });
});
