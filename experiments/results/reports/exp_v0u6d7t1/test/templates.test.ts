import { describe, it, expect } from "vitest";
import { createTemplateEngine } from "../src/templates.js";
import { markdownToHtml } from "../src/markdown.js";
import type { Page } from "../src/types.js";
import path from "node:path";
import fs from "node:fs/promises";
import os from "node:os";

describe("markdownToHtml", () => {
  it("converts basic markdown to HTML", () => {
    const html = markdownToHtml("# Hello\n\nWorld");
    expect(html).toContain("<h1>Hello</h1>");
    expect(html).toContain("<p>World</p>");
  });

  it("highlights code blocks with a known language", () => {
    const html = markdownToHtml("```typescript\nconst x = 1;\n```");
    expect(html).toContain("hljs");
    expect(html).toContain("language-typescript");
  });

  it("renders plain code blocks without language", () => {
    const html = markdownToHtml("```\nplain code\n```");
    expect(html).toContain("<pre><code>");
    expect(html).toContain("plain code");
  });

  it("renders inline code", () => {
    const html = markdownToHtml("Use `const` keyword");
    expect(html).toContain("<code>const</code>");
  });

  it("renders emphasis and strong", () => {
    const html = markdownToHtml("*italic* **bold**");
    expect(html).toContain("<em>italic</em>");
    expect(html).toContain("<strong>bold</strong>");
  });

  it("renders links", () => {
    const html = markdownToHtml("[click](https://example.com)");
    expect(html).toContain('<a href="https://example.com">click</a>');
  });
});

describe("createTemplateEngine", () => {
  it("renders a page with default layout", async () => {
    const tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), "statik-test-"));
    const layoutsDir = path.join(tmpDir, "layouts");
    await fs.mkdir(layoutsDir, { recursive: true });
    await fs.writeFile(layoutsDir + "/default.hbs", `<html><body><h1>{{page.title}}</h1>{{{content}}}</body></html>`);

    const engine = await createTemplateEngine(tmpDir);
    const page: Page = {
      frontmatter: { title: "Test", draft: false },
      content: "",
      html: "<p>Hello</p>",
      sourcePath: "/src/test.md",
      outputPath: "/out/test/index.html",
      url: "/test/",
      tags: [],
      isDraft: false,
    };

    const result = await engine.render(page, "<p>Hello</p>", { site: { title: "Site" } });
    expect(result).toContain("<h1>Test</h1>");
    expect(result).toContain("<p>Hello</p>");

    await fs.rm(tmpDir, { recursive: true, force: true });
  });

  it("renders a page with a custom layout from frontmatter", async () => {
    const tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), "statik-test-"));
    const layoutsDir = path.join(tmpDir, "layouts");
    await fs.mkdir(layoutsDir, { recursive: true });
    await fs.writeFile(layoutsDir + "/default.hbs", `DEFAULT`);
    await fs.writeFile(layoutsDir + "/post.hbs", `<article>{{{content}}}</article>`);

    const engine = await createTemplateEngine(tmpDir);
    const page: Page = {
      frontmatter: { title: "Post", layout: "post", draft: false },
      content: "",
      html: "<p>Body</p>",
      sourcePath: "/src/test.md",
      outputPath: "/out/test/index.html",
      url: "/test/",
      tags: [],
      isDraft: false,
    };

    const result = await engine.render(page, "<p>Body</p>", { site: { title: "S" } });
    expect(result).toContain("<article>");
    expect(result).toContain("<p>Body</p>");

    await fs.rm(tmpDir, { recursive: true, force: true });
  });

  it("renders partials", async () => {
    const tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), "statik-test-"));
    const layoutsDir = path.join(tmpDir, "layouts");
    const partialsDir = path.join(tmpDir, "partials");
    await fs.mkdir(layoutsDir, { recursive: true });
    await fs.mkdir(partialsDir, { recursive: true });
    await fs.writeFile(partialsDir + "/header.hbs", `<header>{{site.title}}</header>`);
    await fs.writeFile(layoutsDir + "/default.hbs", `<html>{{> header}}{{{content}}}</html>`);

    const engine = await createTemplateEngine(tmpDir);
    const page: Page = {
      frontmatter: { title: "Test", draft: false },
      content: "",
      html: "<p>Body</p>",
      sourcePath: "/src/test.md",
      outputPath: "/out/test/index.html",
      url: "/test/",
      tags: [],
      isDraft: false,
    };

    const result = await engine.render(page, "<p>Body</p>", { site: { title: "MySite" } });
    expect(result).toContain("<header>MySite</header>");

    await fs.rm(tmpDir, { recursive: true, force: true });
  });

  it("formatDate helper formats dates", async () => {
    const tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), "statik-test-"));
    const layoutsDir = path.join(tmpDir, "layouts");
    await fs.mkdir(layoutsDir, { recursive: true });
    await fs.writeFile(layoutsDir + "/default.hbs", `{{formatDate page.date}}`);

    const engine = await createTemplateEngine(tmpDir);
    const page: Page = {
      frontmatter: { title: "Test", date: "2024-01-15", draft: false },
      content: "",
      html: "",
      sourcePath: "/src/test.md",
      outputPath: "/out/test/index.html",
      url: "/test/",
      tags: [],
      isDraft: false,
    };

    const result = await engine.render(page, "", { site: { title: "S" } });
    expect(result).toContain("January");
    expect(result).toContain("2024");

    await fs.rm(tmpDir, { recursive: true, force: true });
  });
});
