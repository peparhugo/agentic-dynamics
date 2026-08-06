import { describe, it, expect, beforeAll, afterAll } from "vitest";
import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import { buildSite, slugify } from "../src/build.js";
import { renderMarkdown } from "../src/markdown.js";
import type { SiteConfig } from "../src/types.js";

let root: string;
let config: SiteConfig;

function write(rel: string, content: string) {
  const abs = path.join(root, rel);
  fs.mkdirSync(path.dirname(abs), { recursive: true });
  fs.writeFileSync(abs, content);
}

beforeAll(() => {
  root = fs.mkdtempSync(path.join(os.tmpdir(), "ssgen-build-"));
  config = {
    sourceDir: path.join(root, "content"),
    templateDir: path.join(root, "templates"),
    outDir: path.join(root, "out"),
    includeDrafts: false,
    baseUrl: "https://example.com",
    siteTitle: "Test Site",
    siteDescription: "A test",
  };

  write("templates/default.hbs", `<html><body><h1>{{title}}</h1>{{{content}}}</body></html>`);
  write("templates/tag.hbs", `<ul>{{#each pages}}<li>{{this.title}}</li>{{/each}}</ul>`);
  write("templates/index.hbs", `<div id="idx">{{#each pages}}<a href="{{this.url}}">{{this.title}}</a>{{/each}}</div>`);

  write(
    "content/posts/one.md",
    `---\ntitle: One\ndate: 2026-01-01\ntags: [alpha, beta]\n---\nHello **one**\n\n\`\`\`js\nconst x = 1;\n\`\`\`\n`
  );
  write("content/posts/two.md", `---\ntitle: Two\ndate: 2026-02-01\ntags: [alpha]\n---\nTwo body`);
  write("content/secret.md", `---\ntitle: Secret\ndraft: true\n---\nhidden`);
});

afterAll(() => fs.rmSync(root, { recursive: true, force: true }));

describe("buildSite", () => {
  it("builds pages, excludes drafts, mirrors directory structure", () => {
    const res = buildSite(config);
    expect(res.pages.map((p) => p.frontmatter.title).sort()).toEqual(["One", "Two"]);
    expect(fs.existsSync(path.join(config.outDir, "posts/one.html"))).toBe(true);
    expect(fs.existsSync(path.join(config.outDir, "posts/two.html"))).toBe(true);
    expect(fs.existsSync(path.join(config.outDir, "secret.html"))).toBe(false);
  });

  it("includes drafts with includeDrafts", () => {
    buildSite({ ...config, includeDrafts: true });
    expect(fs.existsSync(path.join(config.outDir, "secret.html"))).toBe(true);
    fs.rmSync(path.join(config.outDir, "secret.html"));
  });

  it("applies layout and highlights code blocks", () => {
    buildSite(config);
    const html = fs.readFileSync(path.join(config.outDir, "posts/one.html"), "utf8");
    expect(html).toContain("<h1>One</h1>");
    expect(html).toContain("<strong>one</strong>");
    expect(html).toContain('class="hljs language-js"');
    expect(html).toContain("hljs-"); // token spans present
  });

  it("generates tag index pages", () => {
    buildSite(config);
    const alpha = fs.readFileSync(path.join(config.outDir, "tags/alpha.html"), "utf8");
    const beta = fs.readFileSync(path.join(config.outDir, "tags/beta.html"), "utf8");
    expect(alpha).toContain("<li>One</li>");
    expect(alpha).toContain("<li>Two</li>");
    expect(beta).toContain("<li>One</li>");
    expect(beta).not.toContain("<li>Two</li>");
  });

  it("generates an index page sorted newest-first", () => {
    buildSite(config);
    const idx = fs.readFileSync(path.join(config.outDir, "index.html"), "utf8");
    expect(idx.indexOf("Two")).toBeLessThan(idx.indexOf("One"));
    expect(idx).toContain('href="/posts/one.html"');
  });

  it("generates a valid RSS feed with absolute links, newest first", () => {
    buildSite(config);
    const rss = fs.readFileSync(path.join(config.outDir, "rss.xml"), "utf8");
    expect(rss).toContain("<rss version=\"2.0\">");
    expect(rss).toContain("<title>Test Site</title>");
    expect(rss).toContain("https://example.com/posts/one.html");
    expect(rss.indexOf("<title>Two</title>")).toBeLessThan(rss.indexOf("<title>One</title>"));
    expect(rss).not.toContain("Secret");
  });
});

describe("renderMarkdown", () => {
  it("escapes unhighlighted fences and renders inline markdown", () => {
    const html = renderMarkdown("```\n<b>raw</b>\n```\n\n*em*");
    expect(html).toContain("&lt;b&gt;raw&lt;/b&gt;");
    expect(html).toContain("<em>em</em>");
  });
});

describe("slugify", () => {
  it("normalizes tags to url-safe slugs", () => {
    expect(slugify("C++ / Systems")).toBe("c-systems");
    expect(slugify("  Web Dev  ")).toBe("web-dev");
  });
});
