import { describe, it, expect } from "vitest";
import { execSync } from "node:child_process";
import fs from "node:fs/promises";
import path from "node:path";
import os from "node:os";

async function buildProject(siteTitle = "TestSite", siteUrl = "https://example.com"): Promise<string> {
  const tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), "statik-e2e-"));
  const contentDir = path.join(tmpDir, "content");
  const templatesDir = path.join(tmpDir, "templates");
  const outputDir = path.join(tmpDir, "public");

  await fs.mkdir(contentDir, { recursive: true });

  // Copy templates
  await cpDir(
    path.join(import.meta.dirname, "fixtures/templates"),
    templatesDir,
  );

  // Copy content
  await cpDir(
    path.join(import.meta.dirname, "fixtures/content"),
    contentDir,
  );

  const cliPath = path.join(import.meta.dirname, "..", "dist", "index.js");

  const args = [
    `--source="${contentDir}"`,
    `--templates="${templatesDir}"`,
    `--output="${outputDir}"`,
    `--site-title="${siteTitle}"`,
    `--site-url="${siteUrl}"`,
  ];

  execSync(`node "${cliPath}" ${args.join(" ")}`, { cwd: tmpDir });

  return outputDir;
}

async function cpDir(src: string, dest: string): Promise<void> {
  await fs.mkdir(dest, { recursive: true });
  const entries = await fs.readdir(src, { withFileTypes: true });
  for (const entry of entries) {
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);
    if (entry.isDirectory()) {
      await cpDir(srcPath, destPath);
    } else {
      await fs.copyFile(srcPath, destPath);
    }
  }
}

describe("CLI end-to-end", () => {
  it("builds a site from markdown and templates", async () => {
    const outputDir = await buildProject();
    const files = await fs.readdir(outputDir, { recursive: true, withFileTypes: true });

    const htmlFile = files.find(
      (f) => f.isFile() && f.name === "index.html" && f.parentPath.includes("basic"),
    );
    expect(htmlFile, "should generate an index.html for basic post").toBeTruthy();

    const content = await fs.readFile(
      path.join(htmlFile!.parentPath, "index.html"),
      "utf-8",
    );
    expect(content).toContain("<title>Test Post - TestSite</title>");
    expect(content).toContain("<h1>Test Post</h1>");
    expect(content).toContain("Hello World");
    expect(content).toContain("hljs"); // syntax highlighting
  });

  it("generates RSS feed", async () => {
    const outputDir = await buildProject();
    const feed = await fs.readFile(path.join(outputDir, "feed.xml"), "utf-8");
    expect(feed).toContain("<rss");
    expect(feed).toContain("<channel>");
    expect(feed).toContain("<title>TestSite</title>");
    expect(feed).toContain("<item>");
    expect(feed).toContain("Test Post");
    expect(feed).toContain("<pubDate>");
  });

  it("generates tag index pages", async () => {
    const outputDir = await buildProject("TagTest");
    const tagsDir = path.join(outputDir, "tags");
    const tagsExist = await fs.stat(tagsDir).then(() => true).catch(() => false);
    expect(tagsExist).toBe(true);

    const tagIndex = await fs.readFile(path.join(tagsDir, "index.html"), "utf-8");
    expect(tagIndex).toContain("Tags");
    expect(tagIndex).toContain("javascript");
    expect(tagIndex).toContain("typescript");

    const typescriptTag = await fs.readFile(
      path.join(tagsDir, "typescript", "index.html"),
      "utf-8",
    );
    expect(typescriptTag).toContain("typescript");
    expect(typescriptTag).toContain("Test Post");
  });

  it("respects CLI flag: --site-title", async () => {
    const outputDir = await buildProject("CustomSiteName");
    const feed = await fs.readFile(path.join(outputDir, "feed.xml"), "utf-8");
    expect(feed).toContain("<title>CustomSiteName</title>");
  });

  it("respects CLI flag: --site-url", async () => {
    const outputDir = await buildProject("Test", "https://mycustomdomain.com");
    const feed = await fs.readFile(path.join(outputDir, "feed.xml"), "utf-8");
    expect(feed).toContain("https://mycustomdomain.com");
  });

  it("produces valid HTML structure", async () => {
    const outputDir = await buildProject();
    const files = await fs.readdir(outputDir, { recursive: true, withFileTypes: true });
    const htmlFile = files.find(
      (f) => f.isFile() && f.name === "index.html" && f.parentPath.includes("basic"),
    );
    const html = await fs.readFile(path.join(htmlFile!.parentPath, "index.html"), "utf-8");
    expect(html.trim()).toMatch(/^<!DOCTYPE html>/);
    expect(html).toContain("</html>");
  });

  it("renders partials in output", async () => {
    const outputDir = await buildProject();
    const files = await fs.readdir(outputDir, { recursive: true, withFileTypes: true });
    const htmlFile = files.find(
      (f) => f.isFile() && f.name === "index.html" && f.parentPath.includes("basic"),
    );
    const html = await fs.readFile(path.join(htmlFile!.parentPath, "index.html"), "utf-8");
    expect(html).toContain("<nav>");
    expect(html).toContain('/tags/"');
    expect(html).toContain('/feed.xml"');
  });
});
