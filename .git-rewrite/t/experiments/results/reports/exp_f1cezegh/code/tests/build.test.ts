import { describe, it, expect, beforeAll, afterAll } from "vitest";
import * as fs from "fs";
import * as path from "path";
import * as os from "os";
import { build } from "../src/build";
import { SiteConfig } from "../src/types";

describe("build", () => {
  let tmpDir: string;
  let sourceDir: string;
  let templateDir: string;
  let outputDir: string;

  beforeAll(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "ssg-build-"));
    sourceDir = path.join(tmpDir, "src");
    templateDir = path.join(tmpDir, "templates");
    outputDir = path.join(tmpDir, "out");

    fs.mkdirSync(sourceDir, { recursive: true });
    fs.mkdirSync(templateDir, { recursive: true });
  });

  afterAll(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  function makeConfig(overrides: Partial<SiteConfig> = {}): SiteConfig {
    return {
      sourceDir,
      outputDir,
      templateDir,
      siteTitle: "Test Site",
      siteUrl: "https://test.example.com",
      siteDescription: "A test site",
      port: 8080,
      ...overrides,
    };
  }

  it("builds a basic site from markdown files", async () => {
    fs.writeFileSync(
      path.join(sourceDir, "hello.md"),
      `---
title: Hello World
date: 2024-01-15
tags: [greeting]
---
# Hello

This is a **test** post.

\`\`\`typescript
const x: number = 42;
\`\`\`
`
    );

    fs.writeFileSync(
      path.join(templateDir, "post.hbs"),
      `<html><head><title>{{title}}</title></head><body><h1>{{title}}</h1>{{{body}}}</body></html>`
    );

    await build(makeConfig());

    const outFile = path.join(outputDir, "hello.html");
    expect(fs.existsSync(outFile)).toBe(true);

    const content = fs.readFileSync(outFile, "utf-8");
    expect(content).toContain("Hello World");
    expect(content).toContain('<span class="hljs-title class_">42</span>');
  });

  it("generates index.html", async () => {
    fs.writeFileSync(
      path.join(sourceDir, "a.md"),
      `---
title: Post A
date: 2024-01-01
---
Content A.`
    );
    fs.writeFileSync(
      path.join(sourceDir, "b.md"),
      `---
title: Post B
date: 2024-02-01
---
Content B.`
    );

    await build(makeConfig());

    const indexFile = path.join(outputDir, "index.html");
    expect(fs.existsSync(indexFile)).toBe(true);
    const indexContent = fs.readFileSync(indexFile, "utf-8");
    expect(indexContent).toContain("Post A");
    expect(indexContent).toContain("Post B");
  });

  it("excludes draft pages from built output", async () => {
    fs.writeFileSync(
      path.join(sourceDir, "visible.md"),
      `---
title: Visible
---
Content.`
    );
    fs.writeFileSync(
      path.join(sourceDir, "hidden.md"),
      `---
title: Hidden
draft: true
---
Secret.`
    );

    await build(makeConfig());

    expect(fs.existsSync(path.join(outputDir, "visible.html"))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, "hidden.html"))).toBe(false);
  });

  it("generates tag index pages", async () => {
    fs.writeFileSync(
      path.join(sourceDir, "tagged.md"),
      `---
title: Tagged Post
date: 2024-03-01
tags: [typescript, node]
---
Tagged content.`
    );

    await build(makeConfig());

    const tsTagFile = path.join(outputDir, "tags", "typescript.html");
    const nodeTagFile = path.join(outputDir, "tags", "node.html");
    expect(fs.existsSync(tsTagFile)).toBe(true);
    expect(fs.existsSync(nodeTagFile)).toBe(true);

    const tsContent = fs.readFileSync(tsTagFile, "utf-8");
    expect(tsContent).toContain("Tagged Post");
  });

  it("generates RSS feed", async () => {
    fs.writeFileSync(
      path.join(sourceDir, "rss-post.md"),
      `---
title: RSS Post
date: 2024-04-01
---
For the feed.`
    );

    await build(makeConfig());

    const rssFile = path.join(outputDir, "rss.xml");
    expect(fs.existsSync(rssFile)).toBe(true);
    const rssContent = fs.readFileSync(rssFile, "utf-8");
    expect(rssContent).toContain("RSS Post");
    expect(rssContent).toContain("<?xml");
  });

  it("uses layout template when available", async () => {
    fs.writeFileSync(
      path.join(templateDir, "layout.hbs"),
      `<html><body><header>Site Header</header>{{{body}}}<footer>Site Footer</footer></body></html>`
    );
    fs.writeFileSync(
      path.join(sourceDir, "layout-test.md"),
      `---
title: Layout Post
---
Content with layout.`
    );

    await build(makeConfig());

    const outContent = fs.readFileSync(
      path.join(outputDir, "layout-test.html"),
      "utf-8"
    );
    expect(outContent).toContain("Site Header");
    expect(outContent).toContain("Site Footer");
    expect(outContent).toContain("Layout Post");
  });

  it("handles nested source directories", async () => {
    const nestedDir = path.join(sourceDir, "blog", "2024");
    fs.mkdirSync(nestedDir, { recursive: true });
    fs.writeFileSync(
      path.join(nestedDir, "nested.md"),
      `---
title: Nested Post
---
Nested content.`
    );

    await build(makeConfig());

    const outFile = path.join(outputDir, "blog", "2024", "nested.html");
    expect(fs.existsSync(outFile)).toBe(true);
  });

  it("uses custom template for index when available", async () => {
    fs.writeFileSync(
      path.join(templateDir, "index.hbs"),
      `<html><body><h1>{{siteTitle}}</h1><ul>{{#each pages}}<li><a href="{{url}}">{{title}}</a></li>{{/each}}</ul></body></html>`
    );

    await build(makeConfig());

    const indexContent = fs.readFileSync(
      path.join(outputDir, "index.html"),
      "utf-8"
    );
    expect(indexContent).toContain("<h1>Test Site</h1>");
  });
});
