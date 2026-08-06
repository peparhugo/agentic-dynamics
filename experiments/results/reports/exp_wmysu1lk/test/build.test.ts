import { describe, it, expect } from "vitest";
import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import { build } from "../src/build";

describe("build", () => {
  it("builds a site from fixtures", () => {
    const sourceDir = path.join(__dirname, "fixtures", "posts");
    const templateDir = path.join(__dirname, "fixtures", "templates");
    const outputDir = fs.mkdtempSync(path.join(os.tmpdir(), "statik-out-"));

    const count = build({
      sourceDir,
      templateDir,
      outputDir,
      config: { title: "Test Site", description: "", url: "", author: "" },
    });

    // 3 published posts (hello, another, notags), draft is excluded
    expect(count).toBe(3);

    // index.html
    const index = fs.readFileSync(
      path.join(outputDir, "index.html"),
      "utf-8"
    );
    expect(index).toContain("Hello World");
    expect(index).toContain("Another Post");
    expect(index).toContain("No Tags Post");
    expect(index).not.toContain("Secret Post");

    // post pages
    const helloHtml = fs.readFileSync(
      path.join(outputDir, "posts", "hello", "index.html"),
      "utf-8"
    );
    expect(helloHtml).toContain("Hello World");
    expect(helloHtml).toContain("hljs");

    // tag pages
    const jsTag = fs.readFileSync(
      path.join(outputDir, "tags", "javascript", "index.html"),
      "utf-8"
    );
    expect(jsTag).toContain("Hello World");
    expect(jsTag).toContain("Another Post");

    const tsTag = fs.readFileSync(
      path.join(outputDir, "tags", "typescript", "index.html"),
      "utf-8"
    );
    expect(tsTag).toContain("Another Post");

    // tags index
    const tagsIndex = fs.readFileSync(
      path.join(outputDir, "tags", "index.html"),
      "utf-8"
    );
    expect(tagsIndex).toContain("javascript (2)");
    expect(tagsIndex).toContain("typescript (1)");

    // RSS feed
    const rss = fs.readFileSync(
      path.join(outputDir, "feed.xml"),
      "utf-8"
    );
    expect(rss).toContain("<rss");
    expect(rss).toContain("Hello World");
    expect(rss).not.toContain("Secret Post");

    // site.json
    const siteConfig = JSON.parse(
      fs.readFileSync(path.join(outputDir, "site.json"), "utf-8")
    );
    expect(siteConfig.title).toBe("Test Site");

    fs.rmSync(outputDir, { recursive: true });
  });

  it("excludes draft posts", () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), "statik-draft-"));
    const srcDir = path.join(dir, "content");
    fs.mkdirSync(srcDir);

    fs.writeFileSync(
      path.join(srcDir, "visible.md"),
      "---\ntitle: V\ndate: 2024-01-01\n---\nContent"
    );
    fs.writeFileSync(
      path.join(srcDir, "hidden.md"),
      "---\ntitle: H\ndate: 2024-01-01\ndraft: true\n---\nContent"
    );

    const tmplDir = path.join(__dirname, "fixtures", "templates");
    const outDir = path.join(dir, "out");

    const count = build({
      sourceDir: srcDir,
      templateDir: tmplDir,
      outputDir: outDir,
      config: { title: "", description: "", url: "", author: "" },
    });

    expect(count).toBe(1);
    const index = fs.readFileSync(
      path.join(outDir, "index.html"),
      "utf-8"
    );
    expect(index).toContain("V");
    expect(index).not.toContain("H");

    fs.rmSync(dir, { recursive: true });
  });

  it("returns 0 for empty source directory", () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), "statik-empty-"));
    const srcDir = path.join(dir, "content");
    fs.mkdirSync(srcDir);
    const tmplDir = path.join(__dirname, "fixtures", "templates");
    const outDir = path.join(dir, "out");

    const count = build({
      sourceDir: srcDir,
      templateDir: tmplDir,
      outputDir: outDir,
      config: { title: "", description: "", url: "", author: "" },
    });

    expect(count).toBe(0);

    fs.rmSync(dir, { recursive: true });
  });
});
