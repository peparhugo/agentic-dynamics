import { describe, it, expect, beforeEach, afterEach } from "vitest";
import path from "path";
import fs from "fs";
import os from "os";
import { generate } from "../src/generator";

describe("generate", () => {
  let outputDir: string;

  beforeEach(() => {
    outputDir = fs.mkdtempSync(path.join(os.tmpdir(), "ssg-test-"));
  });

  afterEach(() => {
    if (fs.existsSync(outputDir)) {
      fs.rmSync(outputDir, { recursive: true });
    }
  });

  const sourceDir = path.join(__dirname, "fixtures", "source");
  const templateDir = path.join(__dirname, "fixtures", "templates");

  it("generates HTML files for published markdown pages", () => {
    generate({
      sourceDir,
      templateDir,
      outputDir,
      siteConfig: {
        title: "Test Site",
        description: "A test",
        url: "http://localhost:3000",
      },
    });

    const helloPath = path.join(outputDir, "posts", "hello-world", "index.html");
    expect(fs.existsSync(helloPath)).toBe(true);
    const content = fs.readFileSync(helloPath, "utf-8");
    expect(content).toContain("Hello World");
    expect(content).toContain("Test Site");
  });

  it("does not generate pages for draft posts", () => {
    generate({
      sourceDir,
      templateDir,
      outputDir,
      siteConfig: {
        title: "Test Site",
        description: "A test",
        url: "http://localhost:3000",
      },
    });

    const draftPath = path.join(outputDir, "posts", "draft-post", "index.html");
    expect(fs.existsSync(draftPath)).toBe(false);
  });

  it("generates tag index pages", () => {
    generate({
      sourceDir,
      templateDir,
      outputDir,
      siteConfig: {
        title: "Test Site",
        description: "A test",
        url: "http://localhost:3000",
      },
    });

    const jsTagPath = path.join(outputDir, "tags", "javascript", "index.html");
    expect(fs.existsSync(jsTagPath)).toBe(true);
    const content = fs.readFileSync(jsTagPath, "utf-8");
    expect(content).toContain("javascript");
  });

  it("generates RSS feed", () => {
    generate({
      sourceDir,
      templateDir,
      outputDir,
      siteConfig: {
        title: "Test Site",
        description: "A test",
        url: "http://localhost:3000",
      },
    });

    const rssPath = path.join(outputDir, "feed.xml");
    expect(fs.existsSync(rssPath)).toBe(true);
    const content = fs.readFileSync(rssPath, "utf-8");
    expect(content).toContain('<?xml version="1.0"');
    expect(content).toContain("<rss version=\"2.0\"");
    expect(content).toContain("<title>Test Site</title>");
  });

  it("renders markdown to HTML with heading tags", () => {
    generate({
      sourceDir,
      templateDir,
      outputDir,
      siteConfig: {
        title: "Test Site",
        description: "A test",
        url: "http://localhost:3000",
      },
    });

    const helloPath = path.join(outputDir, "posts", "hello-world", "index.html");
    const content = fs.readFileSync(helloPath, "utf-8");
    expect(content).toContain("<h1>Hello World</h1>");
  });

  it("uses custom layout from frontmatter", () => {
    generate({
      sourceDir,
      templateDir,
      outputDir,
      siteConfig: {
        title: "Test Site",
        description: "A test",
        url: "http://localhost:3000",
      },
    });

    const aboutPath = path.join(outputDir, "pages", "about", "index.html");
    expect(fs.existsSync(aboutPath)).toBe(true);
    const content = fs.readFileSync(aboutPath, "utf-8");
    expect(content).toContain("About");
  });

  it("clears output directory before regenerating", () => {
    const extraFile = path.join(outputDir, "stale.txt");
    fs.mkdirSync(outputDir, { recursive: true });
    fs.writeFileSync(extraFile, "stale");

    generate({
      sourceDir,
      templateDir,
      outputDir,
      siteConfig: {
        title: "Test Site",
        description: "A test",
        url: "http://localhost:3000",
      },
    });

    expect(fs.existsSync(extraFile)).toBe(false);
  });
});
