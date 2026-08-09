import { describe, it, expect, beforeAll, afterAll } from "vitest";
import fs from "node:fs/promises";
import path from "node:path";
import os from "node:os";
import { buildSite } from "../src/builder.js";
import { generateRSS } from "../src/rss.js";
import type { SiteConfig, Page } from "../src/types.js";

async function setupDirs() {
  const baseDir = await fs.mkdtemp(path.join(os.tmpdir(), "ssg-test-"));
  const srcDir = path.join(baseDir, "content");
  const tmplDir = path.join(baseDir, "templates");
  const outDir = path.join(baseDir, "output");

  await fs.mkdir(srcDir, { recursive: true });
  await fs.mkdir(tmplDir, { recursive: true });
  await fs.mkdir(outDir, { recursive: true });

  await fs.writeFile(
    path.join(tmplDir, "layout.hbs"),
    `<html><head><title>{{title}}</title></head><body><h1>{{title}}</h1>{{{content}}}<p>Tags: {{#each tags}}{{this}} {{/each}}</p></body></html>`,
  );
  await fs.writeFile(
    path.join(tmplDir, "index.hbs"),
    `<html><body><h1>{{config.title}}</h1><ul>{{#each pages}}<li><a href="{{slug}}.html">{{frontmatter.title}}</a></li>{{/each}}</ul></body></html>`,
  );
  await fs.writeFile(
    path.join(tmplDir, "tag.hbs"),
    `<html><body><h1>Tag: {{tag}}</h1><ul>{{#each pages}}<li>{{frontmatter.title}}</li>{{/each}}</ul></body></html>`,
  );

  return { baseDir, srcDir, tmplDir, outDir };
}

describe("builder integration", () => {
  let dirs: Awaited<ReturnType<typeof setupDirs>>;

  beforeAll(async () => {
    dirs = await setupDirs();
  });

  afterAll(async () => {
    await fs.rm(dirs.baseDir, { recursive: true, force: true });
  });

  it("builds a site from markdown files", async () => {
    await fs.writeFile(
      path.join(dirs.srcDir, "hello.md"),
      `---
title: Hello World
date: 2024-06-15
tags:
  - intro
---
# Welcome

This is a test post.`,
    );

    const config: SiteConfig = {
      title: "Test Site",
      description: "Testing SSG",
      baseUrl: "http://localhost:8080",
      sourceDir: dirs.srcDir,
      templateDir: dirs.tmplDir,
      outputDir: dirs.outDir,
    };

    await buildSite(config);

    const outputFile = path.join(dirs.outDir, "hello.html");
    const content = await fs.readFile(outputFile, "utf-8");
    expect(content).toContain("<h1>Hello World</h1>");
    expect(content).toContain("<h1>Welcome</h1>");
    expect(content).toContain("<p>This is a test post.</p>");
    expect(content).toContain("intro");
  });

  it("generates index page", async () => {
    const outputDir = path.join(dirs.baseDir, "output2");
    await fs.mkdir(outputDir, { recursive: true });

    await fs.writeFile(
      path.join(dirs.srcDir, "post1.md"),
      `---
title: Post One
date: 2024-01-01
---
Post one content.`,
    );

    const config: SiteConfig = {
      title: "My Blog",
      description: "Blog",
      baseUrl: "http://localhost:8080",
      sourceDir: dirs.srcDir,
      templateDir: dirs.tmplDir,
      outputDir,
    };

    await buildSite(config);

    const indexContent = await fs.readFile(
      path.join(outputDir, "index.html"),
      "utf-8",
    );
    expect(indexContent).toContain("My Blog");
    expect(indexContent).toContain("Post One");
    expect(indexContent).toContain("Hello World");
  });

  it("generates tag pages", async () => {
    const outputDir = path.join(dirs.baseDir, "output3");
    await fs.mkdir(outputDir, { recursive: true });

    const config: SiteConfig = {
      title: "Tagged Site",
      description: "",
      baseUrl: "http://localhost:8080",
      sourceDir: dirs.srcDir,
      templateDir: dirs.tmplDir,
      outputDir,
    };

    await buildSite(config);

    const tagDir = path.join(outputDir, "tags");
    const entries = await fs.readdir(tagDir);
    expect(entries.length).toBeGreaterThan(0);

    const tagFile = path.join(tagDir, entries[0]);
    const tagContent = await fs.readFile(tagFile, "utf-8");
    expect(tagContent).toContain("Tag:");
  });

  it("generates RSS feed", async () => {
    const outputDir = path.join(dirs.baseDir, "output4");
    await fs.mkdir(outputDir, { recursive: true });

    const config: SiteConfig = {
      title: "RSS Site",
      description: "RSS Test",
      baseUrl: "http://localhost:8080",
      sourceDir: dirs.srcDir,
      templateDir: dirs.tmplDir,
      outputDir,
    };

    await buildSite(config);

    const rssContent = await fs.readFile(
      path.join(outputDir, "rss.xml"),
      "utf-8",
    );
    expect(rssContent).toContain('<?xml version="1.0"');
    expect(rssContent).toContain("<rss");
    expect(rssContent).toContain("<channel>");
  });

  it("skips draft posts in output", async () => {
    const outputDir = path.join(dirs.baseDir, "output5");
    await fs.mkdir(outputDir, { recursive: true });

    await fs.writeFile(
      path.join(dirs.srcDir, "draft-post.md"),
      `---
title: Secret Draft
draft: true
---
This should not appear.`,
    );

    await fs.writeFile(
      path.join(dirs.srcDir, "pub-post.md"),
      `---
title: Published Post
---
This should appear.`,
    );

    const config: SiteConfig = {
      title: "Draft Test",
      description: "",
      baseUrl: "http://localhost:8080",
      sourceDir: dirs.srcDir,
      templateDir: dirs.tmplDir,
      outputDir,
    };

    await buildSite(config);

    const indexContent = await fs.readFile(
      path.join(outputDir, "index.html"),
      "utf-8",
    );
    expect(indexContent).not.toContain("Secret Draft");
    expect(indexContent).toContain("Published Post");

    await expect(
      fs.access(path.join(outputDir, "draft-post.html")),
    ).rejects.toThrow();
  });

  it("handles nested source directories", async () => {
    const outputDir = path.join(dirs.baseDir, "output6");
    await fs.mkdir(outputDir, { recursive: true });

    const nestedDir = path.join(dirs.srcDir, "blog");
    await fs.mkdir(nestedDir, { recursive: true });
    await fs.writeFile(
      path.join(nestedDir, "nested.md"),
      `---
title: Nested Post
---
Nested content.`,
    );

    const config: SiteConfig = {
      title: "Nested",
      description: "",
      baseUrl: "http://localhost:8080",
      sourceDir: dirs.srcDir,
      templateDir: dirs.tmplDir,
      outputDir,
    };

    await buildSite(config);

    const nestedOutput = path.join(outputDir, "blog", "nested.html");
    const content = await fs.readFile(nestedOutput, "utf-8");
    expect(content).toContain("Nested Post");
  });
});
