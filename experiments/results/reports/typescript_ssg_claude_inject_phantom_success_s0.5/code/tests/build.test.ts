import { describe, it, expect, beforeEach, afterEach } from "vitest";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { buildSite, collectTags, loadPages, slugify } from "../src/build.js";
import { renderMarkdown } from "../src/markdown.js";
import { generateRss } from "../src/rss.js";
import type { SiteConfig } from "../src/types.js";

let root: string;
let config: SiteConfig;

function write(rel: string, content: string): void {
  const full = path.join(root, rel);
  fs.mkdirSync(path.dirname(full), { recursive: true });
  fs.writeFileSync(full, content);
}

beforeEach(() => {
  root = fs.mkdtempSync(path.join(os.tmpdir(), "ssg-build-"));
  config = {
    sourceDir: path.join(root, "content"),
    templateDir: path.join(root, "templates"),
    outDir: path.join(root, "out"),
    baseUrl: "https://example.com",
    siteTitle: "Test Site",
    siteDescription: "A test",
    includeDrafts: false,
  };
  write(
    "content/posts/hello.md",
    `---\ntitle: Hello\ndate: 2024-02-01\ntags: [typescript, web dev]\n---\n# Hi\n\n\`\`\`js\nconst x = 1;\n\`\`\`\n`
  );
  write("content/posts/older.md", `---\ntitle: Older\ndate: 2023-01-01\ntags: [typescript]\n---\nold`);
  write("content/secret.md", `---\ntitle: Secret\ndraft: true\ntags: [typescript]\n---\nshh`);
});

afterEach(() => fs.rmSync(root, { recursive: true, force: true }));

describe("loadPages", () => {
  it("excludes drafts by default and sorts newest first", () => {
    const pages = loadPages(config);
    expect(pages.map((p) => p.frontmatter.title)).toEqual(["Hello", "Older"]);
  });

  it("includes drafts with includeDrafts", () => {
    const pages = loadPages({ ...config, includeDrafts: true });
    expect(pages.map((p) => p.frontmatter.title)).toContain("Secret");
  });

  it("computes pretty URLs and output paths", () => {
    const pages = loadPages(config);
    const hello = pages.find((p) => p.frontmatter.title === "Hello")!;
    expect(hello.url).toBe("/posts/hello/");
    expect(hello.outputPath).toBe(path.join("posts", "hello", "index.html"));
  });
});

describe("markdown + highlighting", () => {
  it("renders headings and syntax-highlighted code blocks", () => {
    const html = renderMarkdown("# Title\n\n```js\nconst x = 1;\n```\n");
    expect(html).toContain("<h1>Title</h1>");
    expect(html).toContain('class="hljs language-js"');
    expect(html).toContain("hljs-keyword");
  });
});

describe("buildSite", () => {
  it("writes page HTML, index, tag pages, and RSS", () => {
    const result = buildSite(config);
    const out = config.outDir;
    expect(fs.existsSync(path.join(out, "posts", "hello", "index.html"))).toBe(true);
    expect(fs.existsSync(path.join(out, "index.html"))).toBe(true);
    expect(fs.existsSync(path.join(out, "tags", "typescript", "index.html"))).toBe(true);
    expect(fs.existsSync(path.join(out, "tags", "web-dev", "index.html"))).toBe(true);
    expect(fs.existsSync(path.join(out, "feed.xml"))).toBe(true);
    expect(result.tagPages).toEqual(["/tags/typescript/", "/tags/web-dev/"]);
  });

  it("tag index lists only tagged, non-draft pages", () => {
    buildSite(config);
    const html = fs.readFileSync(path.join(config.outDir, "tags", "typescript", "index.html"), "utf8");
    expect(html).toContain("Hello");
    expect(html).toContain("Older");
    expect(html).not.toContain("Secret");
  });

  it("uses custom templates when provided", () => {
    write("templates/layouts/default.hbs", "<body data-layout>{{{body}}}</body>");
    write("templates/post.hbs", "<main>{{page.frontmatter.title}}</main>");
    buildSite(config);
    const html = fs.readFileSync(path.join(config.outDir, "posts", "hello", "index.html"), "utf8");
    expect(html).toContain("<body data-layout>");
    expect(html).toContain("<main>Hello</main>");
  });
});

describe("collectTags / slugify", () => {
  it("groups pages by tag alphabetically", () => {
    const tags = collectTags(loadPages(config));
    expect([...tags.keys()]).toEqual(["typescript", "web dev"]);
    expect(tags.get("typescript")!.length).toBe(2);
  });

  it("slugifies tags", () => {
    expect(slugify("Web Dev!")).toBe("web-dev");
    expect(slugify("C++ & Rust")).toBe("c-rust");
  });
});

describe("generateRss", () => {
  it("produces valid RSS with escaped fields and pubDates", () => {
    const pages = loadPages(config);
    const xml = generateRss(pages, config);
    expect(xml).toContain("<?xml version=");
    expect(xml).toContain("<title>Test Site</title>");
    expect(xml).toContain("<link>https://example.com/posts/hello/</link>");
    expect(xml).toContain("<pubDate>Thu, 01 Feb 2024");
    expect(xml).toContain("<category>typescript</category>");
    expect(xml).toContain("<![CDATA[");
  });

  it("escapes XML entities in titles", () => {
    write("content/amp.md", `---\ntitle: "Cats & <Dogs>"\ndate: 2024-05-05\n---\nx`);
    const xml = generateRss(loadPages(config), config);
    expect(xml).toContain("Cats &amp; &lt;Dogs&gt;");
  });

  it("respects the item limit", () => {
    const xml = generateRss(loadPages(config), config, 1);
    expect(xml.match(/<item>/g)?.length).toBe(1);
  });
});
