import { describe, it, expect, beforeEach, afterEach } from "vitest";
import * as fs from "fs";
import * as path from "path";
import * as os from "os";
import { Generator } from "../src/generator";
import { GeneratorConfig } from "../src/types";

describe("Generator", () => {
  let tmpDir: string;
  let sourceDir: string;
  let templateDir: string;
  let outputDir: string;

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "triton-gen-"));
    sourceDir = path.join(tmpDir, "source");
    templateDir = path.join(tmpDir, "templates");
    outputDir = path.join(tmpDir, "output");
    fs.mkdirSync(sourceDir, { recursive: true });
    fs.mkdirSync(templateDir, { recursive: true });
    fs.mkdirSync(path.join(templateDir, "partials"), { recursive: true });
  });

  afterEach(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  function makeConfig(overrides: Partial<GeneratorConfig> = {}): GeneratorConfig {
    return {
      sourceDir,
      templateDir,
      outputDir,
      siteTitle: "Test Site",
      siteUrl: "http://example.com",
      dev: false,
      port: 3000,
      ...overrides,
    };
  }

  function writeSource(relPath: string, content: string): string {
    const fullPath = path.join(sourceDir, relPath);
    fs.mkdirSync(path.dirname(fullPath), { recursive: true });
    fs.writeFileSync(fullPath, content);
    return fullPath;
  }

  function writeTemplate(name: string, content: string): void {
    const fullPath = path.join(templateDir, name);
    fs.mkdirSync(path.dirname(fullPath), { recursive: true });
    fs.writeFileSync(fullPath, content);
  }

  it("generates HTML pages from markdown", () => {
    writeSource("hello.md", `---
title: Hello
date: 2025-01-01
---
# Hello World

This is a post.`);

    writeTemplate("default.hbs", '<!DOCTYPE html><html><body>{{{content}}}</body></html>');
    writeTemplate("page.hbs", '<article><h1>{{page.title}}</h1>{{{content}}}</article>');

    const generator = new Generator(makeConfig());
    const pages = generator.build();

    expect(pages).toHaveLength(1);
    expect(pages[0].frontmatter.title).toBe("Hello");

    const outFile = path.join(outputDir, "hello.html");
    expect(fs.existsSync(outFile)).toBe(true);

    const html = fs.readFileSync(outFile, "utf-8");
    expect(html).toContain("<h1>Hello</h1>");
    expect(html).toContain("Hello World");
    expect(html).toContain("<!DOCTYPE html>");
  });

  it("filters out draft posts", () => {
    writeSource("published.md", `---
title: Published
---
# Published`);
    writeSource("draft.md", `---
title: Draft
draft: true
---
# Draft`);

    writeTemplate("default.hbs", "{{{content}}}");
    writeTemplate("page.hbs", "{{{content}}}");

    const generator = new Generator(makeConfig());
    const pages = generator.build();

    expect(pages).toHaveLength(1);
    expect(pages[0].frontmatter.title).toBe("Published");

    expect(fs.existsSync(path.join(outputDir, "published.html"))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, "draft.html"))).toBe(false);
  });

  it("generates index page with post listings", () => {
    writeSource("a.md", `---
title: Post A
date: 2025-01-01
---
A`);
    writeSource("b.md", `---
title: Post B
date: 2025-02-01
---
B`);

    writeTemplate("default.hbs", '<!DOCTYPE html><html><body>{{{content}}}</body></html>');
    writeTemplate("page.hbs", "{{{content}}}");
    writeTemplate("index.hbs", '<ul>{{#each pages}}<li><a href="{{url}}">{{title}}</a></li>{{/each}}</ul>');

    const generator = new Generator(makeConfig());
    generator.build();

    const indexPath = path.join(outputDir, "index.html");
    expect(fs.existsSync(indexPath)).toBe(true);

    const html = fs.readFileSync(indexPath, "utf-8");
    expect(html).toContain('<a href="/a.html">Post A</a>');
    expect(html).toContain('<a href="/b.html">Post B</a>');
  });

  it("generates tag index pages", () => {
    writeSource("post1.md", `---
title: Post One
date: 2025-01-01
tags:
  - js
  - css
---
One`);
    writeSource("post2.md", `---
title: Post Two
date: 2025-02-01
tags:
  - js
---
Two`);

    writeTemplate("default.hbs", "{{{content}}}");
    writeTemplate("page.hbs", "{{{content}}}");
    writeTemplate("tag.hbs", '<h1>Tag {{tag}}</h1><ul>{{#each pages}}<li>{{title}}</li>{{/each}}</ul>');

    const generator = new Generator(makeConfig());
    generator.build();

    expect(fs.existsSync(path.join(outputDir, "tags", "js.html"))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, "tags", "css.html"))).toBe(true);

    const jsTagHtml = fs.readFileSync(path.join(outputDir, "tags", "js.html"), "utf-8");
    expect(jsTagHtml).toContain("Post One");
    expect(jsTagHtml).toContain("Post Two");

    const cssTagHtml = fs.readFileSync(path.join(outputDir, "tags", "css.html"), "utf-8");
    expect(cssTagHtml).toContain("Post One");
    expect(cssTagHtml).not.toContain("Post Two");
  });

  it("generates RSS feed", () => {
    writeSource("post.md", `---
title: RSS Post
date: 2025-03-15
---
RSS content.`);

    writeTemplate("default.hbs", "{{{content}}}");
    writeTemplate("page.hbs", "{{{content}}}");

    const generator = new Generator(makeConfig());
    generator.build();

    const rssPath = path.join(outputDir, "rss.xml");
    expect(fs.existsSync(rssPath)).toBe(true);

    const rssContent = fs.readFileSync(rssPath, "utf-8");
    expect(rssContent).toContain("<rss");
    expect(rssContent).toContain("RSS Post");
    expect(rssContent).toContain("RSS content");
  });

  it("copies assets directory", () => {
    writeSource("post.md", `---
title: Post
---
Post`);
    const assetsDir = path.join(sourceDir, "assets");
    fs.mkdirSync(assetsDir, { recursive: true });
    fs.writeFileSync(path.join(assetsDir, "style.css"), "body { color: red; }");

    writeTemplate("default.hbs", "{{{content}}}");
    writeTemplate("page.hbs", "{{{content}}}");

    const generator = new Generator(makeConfig());
    generator.build();

    const cssPath = path.join(outputDir, "style.css");
    expect(fs.existsSync(cssPath)).toBe(true);
    expect(fs.readFileSync(cssPath, "utf-8")).toBe("body { color: red; }");
  });

  it("handles nested source directories", () => {
    writeSource("blog/tech/post.md", `---
title: Tech Post
---
Tech content.`);

    writeTemplate("default.hbs", "{{{content}}}");
    writeTemplate("page.hbs", "{{{content}}}");

    const generator = new Generator(makeConfig());
    generator.build();

    const outFile = path.join(outputDir, "blog", "tech", "post.html");
    expect(fs.existsSync(outFile)).toBe(true);
  });

  it("sorts pages by date descending", () => {
    writeSource("old.md", `---
title: Old
date: 2024-01-01
---
Old`);
    writeSource("new.md", `---
title: New
date: 2025-06-01
---
New`);

    writeTemplate("default.hbs", "{{{content}}}");
    writeTemplate("page.hbs", "{{{content}}}");

    const generator = new Generator(makeConfig());
    const pages = generator.build();

    expect(pages[0].frontmatter.title).toBe("New");
    expect(pages[1].frontmatter.title).toBe("Old");
  });

  it("clears output directory before rebuild", () => {
    writeSource("post.md", `---
title: Post
---
Post`);

    writeTemplate("default.hbs", "{{{content}}}");
    writeTemplate("page.hbs", "{{{content}}}");

    const oldFile = path.join(outputDir, "old.txt");
    fs.mkdirSync(outputDir, { recursive: true });
    fs.writeFileSync(oldFile, "stale");

    const generator = new Generator(makeConfig());
    generator.build();

    expect(fs.existsSync(oldFile)).toBe(false);
    expect(fs.existsSync(path.join(outputDir, "post.html"))).toBe(true);
  });

  it("skips tag index generation when no tag template exists", () => {
    writeSource("post.md", `---
title: Tagged
tags: [js]
---
Content`);

    writeTemplate("default.hbs", "{{{content}}}");
    writeTemplate("page.hbs", "{{{content}}}");

    const generator = new Generator(makeConfig());
    generator.build();

    expect(fs.existsSync(path.join(outputDir, "tags"))).toBe(false);
  });

  it("does not generate RSS when no posts exist", () => {
    writeTemplate("default.hbs", "{{{content}}}");
    writeTemplate("page.hbs", "{{{content}}}");

    const generator = new Generator(makeConfig());
    generator.build();

    expect(fs.existsSync(path.join(outputDir, "rss.xml"))).toBe(false);
  });
});
