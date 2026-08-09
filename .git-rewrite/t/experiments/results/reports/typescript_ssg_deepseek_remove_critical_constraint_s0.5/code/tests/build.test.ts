import { describe, it, expect, beforeEach, afterEach } from "vitest";
import path from "node:path";
import fs from "node:fs";
import os from "node:os";
import { build } from "../src/build";
import { SiteConfig } from "../src/types";

const fixturesDir = path.resolve(__dirname, "../test-fixtures");

function makeConfig(outputDir: string, overrides?: Partial<SiteConfig>): SiteConfig {
  return {
    sourceDir: path.join(fixturesDir, "content"),
    templateDir: path.join(fixturesDir, "templates"),
    outputDir,
    siteTitle: "Test Site",
    siteUrl: "https://example.com",
    port: 3000,
    serve: false,
    watch: false,
    ...overrides,
  };
}

describe("build", () => {
  let outputDir: string;

  beforeEach(() => {
    outputDir = fs.mkdtempSync(path.join(os.tmpdir(), "statico-build-"));
  });

  afterEach(() => {
    fs.rmSync(outputDir, { recursive: true, force: true });
  });

  it("generates HTML files for published posts", async () => {
    await build(makeConfig(outputDir));

    const helloHtml = path.join(outputDir, "hello-world", "index.html");
    expect(fs.existsSync(helloHtml)).toBe(true);

    const content = fs.readFileSync(helloHtml, "utf-8");
    expect(content).toContain("Hello World");
    expect(content).toContain("<html");
    expect(content).toContain("<header>");
    expect(content).toContain("<h1>");
  });

  it("skips draft posts", async () => {
    await build(makeConfig(outputDir));

    const draftHtml = path.join(outputDir, "draft", "index.html");
    expect(fs.existsSync(draftHtml)).toBe(false);
  });

  it("generates index page", async () => {
    await build(makeConfig(outputDir));

    const indexPath = path.join(outputDir, "index.html");
    expect(fs.existsSync(indexPath)).toBe(true);

    const content = fs.readFileSync(indexPath, "utf-8");
    expect(content).toContain("Hello World");
    expect(content).toContain("Another Post");
    expect(content).toContain("Test Site");
  });

  it("generates tag pages", async () => {
    await build(makeConfig(outputDir));

    const helloTag = path.join(outputDir, "tags", "hello.html");
    expect(fs.existsSync(helloTag)).toBe(true);

    const content = fs.readFileSync(helloTag, "utf-8");
    expect(content).toContain("Tag: hello");
    expect(content).toContain("Hello World");
    expect(content).toContain("Another Post");
  });

  it("generates RSS feed", async () => {
    await build(makeConfig(outputDir));

    const rssPath = path.join(outputDir, "rss.xml");
    expect(fs.existsSync(rssPath)).toBe(true);

    const content = fs.readFileSync(rssPath, "utf-8");
    expect(content).toContain("<rss");
    expect(content).toContain("Hello World");
    expect(content).toContain("Another Post");
    expect(content).not.toContain("Draft Post");
  });

  it("injects live reload script when requested", async () => {
    await build(makeConfig(outputDir), true);

    const helloHtml = path.join(outputDir, "hello-world", "index.html");
    const content = fs.readFileSync(helloHtml, "utf-8");
    expect(content).toContain("__livereload");
    expect(content).toContain("WebSocket");
  });

  it("includes syntax highlighting classes in output", async () => {
    await build(makeConfig(outputDir));

    const helloHtml = path.join(outputDir, "hello-world", "index.html");
    const content = fs.readFileSync(helloHtml, "utf-8");
    expect(content).toContain("language-javascript");
    expect(content).toContain("hljs");
  });

  it("creates output directory if missing", async () => {
    const nestedOutput = path.join(outputDir, "nested", "out");
    await build(makeConfig(nestedOutput));
    expect(fs.existsSync(path.join(nestedOutput, "hello-world", "index.html"))).toBe(true);
  });
});
