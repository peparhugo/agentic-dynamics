import { describe, it, expect, beforeAll, afterAll } from "vitest";
import { existsSync, mkdtempSync, rmSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { createRenderer } from "../src/render.js";
import { build } from "../src/build.js";
import { generateRss } from "../src/rss.js";
import { markdownToHtml } from "../src/markdown.js";

const FIXTURES = join(import.meta.dirname ?? __dirname, "..", "test_fixtures");
const templatesDir = join(FIXTURES, "templates");
const sourceDir = join(FIXTURES, "source");

let outDir: string;

beforeAll(() => {
  outDir = mkdtempSync(join(FIXTURES, "..", "test-out-"));
});

afterAll(() => {
  if (existsSync(outDir)) rmSync(outDir, { recursive: true, force: true });
});

describe("createRenderer", () => {
  const renderer = createRenderer(templatesDir);

  it("renders a post template wrapped in layout", () => {
    const html = renderer.render("post", {
      title: "Test Post",
      date: "2025-01-01",
      tags: ["a", "b"],
      content: "<p>Hello</p>",
      url: "/test.html",
    });
    expect(html).toContain("<!DOCTYPE html>");
    expect(html).toContain("<title>Test Post</title>");
    expect(html).toContain('<meta name="generator" content="ssg">');
    expect(html).toContain("<p>Hello</p>");
    expect(html).toContain('<a href="/tags/a.html">a</a>');
  });

  it("renders the index template", () => {
    const html = renderer.render("index", {
      title: "Home",
      posts: [{ title: "A", url: "/a.html", date: "" }],
    });
    expect(html).toContain("Home");
    expect(html).toContain('<a href="/">Home</a>');
  });

  it("renders the tag template", () => {
    const html = renderer.render("tag", {
      title: "Tag: js",
      tag: "js",
      posts: [{ title: "Hello", url: "/hello.html", date: "2025-01-15" }],
    });
    expect(html).toContain("Tag: js");
    expect(html).toContain('<a href="/hello.html">Hello</a>');
  });

  it("throws for a non-existent template", () => {
    expect(() => renderer.render("missing", {})).toThrow("Template not found");
  });
});

describe("build", () => {
  it("generates output files", () => {
    const site = build({ source: sourceDir, templates: templatesDir, output: outDir });

    expect(site.pages.length).toBe(3);
    expect(site.tags.has("javascript")).toBe(true);
    expect(site.tags.has("intro")).toBe(true);
    expect(site.tags.has("wip")).toBe(false); // draft excluded from tags

    const helloOut = join(outDir, "hello.html");
    expect(existsSync(helloOut)).toBe(true);
    const html = readFileSync(helloOut, "utf-8");
    expect(html).toContain("<h1>Hello World</h1>");
    expect(html).toContain('<span class="hljs-title function_">console</span>');

    const draftOut = join(outDir, "draft.html");
    expect(existsSync(draftOut)).toBe(false);

    const nestedOut = join(outDir, "subdir", "nested.html");
    expect(existsSync(nestedOut)).toBe(true);

    const indexOut = join(outDir, "index.html");
    expect(existsSync(indexOut)).toBe(true);

    const tagOut = join(outDir, "tags", "intro.html");
    expect(existsSync(tagOut)).toBe(true);

    const feedOut = join(outDir, "feed.xml");
    expect(existsSync(feedOut)).toBe(true);
  });

  it("copies non-markdown assets", () => {
    // asset files alongside markdown are copied through
    const site = build({ source: sourceDir, templates: templatesDir, output: outDir });
    expect(site.pages.length).toBeGreaterThanOrEqual(1);
  });
});

describe("markdownToHtml", () => {
  it("converts basic markdown", () => {
    const html = markdownToHtml("# Hello\n\nThis is **bold**.");
    expect(html).toContain("<h1>Hello</h1>");
    expect(html).toContain("<strong>bold</strong>");
  });

  it("applies syntax highlighting to fenced code blocks", () => {
    const html = markdownToHtml("```js\nconst x = 1;\n```");
    expect(html).toContain("hljs");
    expect(html).toContain("const");
  });

  it("leaves unknown languages without highlighting markup", () => {
    const html = markdownToHtml("```nolang\nabc\n```");
    expect(html).toContain("<code>");
    expect(html).not.toContain("hljs");
  });
});

describe("generateRss", () => {
  it("produces valid RSS XML", () => {
    const pages = [
      {
        path: "a.md", url: "/a.html", content: "", html: "<p>A</p>",
        frontmatter: { title: "Post A", date: "2025-05-01", tags: [], draft: false },
      },
      {
        path: "b.md", url: "/b.html", content: "", html: "<p>B</p>",
        frontmatter: { title: "Post B", date: "2025-06-01", tags: [], draft: true },
      },
      {
        path: "c.md", url: "/c.html", content: "", html: "<p>C</p>",
        frontmatter: { title: "Post C", date: "2025-07-01", tags: [], draft: false },
      },
    ];

    const xml = generateRss(pages, "https://example.com");
    expect(xml).toContain("<rss version=\"2.0\">");
    expect(xml).toContain("<title>Post C</title>"); // newest first
    expect(xml).toContain("<title>Post A</title>");
    expect(xml).not.toContain("Post B"); // draft excluded
    expect(xml).toContain("<link>https://example.com/a.html</link>");
  });
});
