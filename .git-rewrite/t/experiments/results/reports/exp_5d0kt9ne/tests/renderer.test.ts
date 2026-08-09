import { describe, it, expect, beforeAll } from "vitest";
import { configureTemplateEngine, renderPage, buildTagMap, generateTagIndex } from "../src/renderer";
import { configureMarked, markdownToHtml } from "../src/highlight";
import { Page, GeneratorOptions, SiteConfig } from "../src/types";
import fs from "fs";
import path from "path";
import os from "os";

const defaultConfig: SiteConfig = { siteName: "Test", siteUrl: "http://localhost" };

function makeOpts(templateDir: string): GeneratorOptions {
  return { sourceDir: "", templateDir, outputDir: "", config: defaultConfig };
}

describe("template rendering", () => {
  let templateDir: string;

  beforeAll(() => {
    templateDir = fs.mkdtempSync(path.join(os.tmpdir(), "ss-tpl-"));
  });

  it("renders with layout wrapping body", () => {
    // Write layout.hbs
    fs.writeFileSync(
      path.join(templateDir, "layout.hbs"),
      '<!DOCTYPE html><html><head><title>{{title}}</title></head><body><main>{{{body}}}</main></body></html>'
    );

    const layout = configureTemplateEngine(templateDir);
    expect(layout).not.toBeNull();

    const page: Page = {
      path: "/hello/",
      sourcePath: "/src/hello.md",
      frontmatter: { title: "Hello World", date: "2024-01-01" },
      content: "markdown",
      html: "<p>Hello content</p>",
    };

    const result = renderPage(page, [page], templateDir, layout, makeOpts(templateDir));
    expect(result).toContain("<!DOCTYPE html>");
    expect(result).toContain("<title>Hello World</title>");
    expect(result).toContain("<p>Hello content</p>");
    expect(result).toContain("<main>");
  });

  it("uses page-specific template when frontmatter.template is set", () => {
    fs.writeFileSync(
      path.join(templateDir, "post.hbs"),
      '<article class="post"><h1>{{title}}</h1>{{{content}}}</article>'
    );

    const layout = configureTemplateEngine(templateDir);
    const page: Page = {
      path: "/post/",
      sourcePath: "/src/post.md",
      frontmatter: { title: "My Post", template: "post.hbs" },
      content: "markdown",
      html: "<p>Body</p>",
    };

    const result = renderPage(page, [page], templateDir, layout, makeOpts(templateDir));
    expect(result).toContain('<article class="post">');
    expect(result).toContain("<h1>My Post</h1>");
    expect(result).toContain("<p>Body</p>");
  });

  it("registers and uses partials", () => {
    const partialsDir = path.join(templateDir, "partials");
    fs.mkdirSync(partialsDir, { recursive: true });
    fs.writeFileSync(path.join(partialsDir, "header.hbs"), '<header>{{site.siteName}}</header>');

    fs.writeFileSync(
      path.join(templateDir, "layout.hbs"),
      '<!DOCTYPE html>{{> header}}{{{body}}}</html>'
    );

    const layout = configureTemplateEngine(templateDir);
    const page: Page = {
      path: "/",
      sourcePath: "/src/index.md",
      frontmatter: { title: "Home" },
      content: "",
      html: "<p>Home page</p>",
    };

    const result = renderPage(page, [page], templateDir, layout, makeOpts(templateDir));
    expect(result).toContain("<header>Test</header>");
  });

  it("passes pages list to template context", () => {
    fs.writeFileSync(
      path.join(templateDir, "layout.hbs"),
      '<!DOCTYPE html><nav>{{#each pages}}<a href="{{path}}">{{title}}</a>{{/each}}</nav>{{{body}}}</html>'
    );

    const layout = configureTemplateEngine(templateDir);
    const pages: Page[] = [
      { path: "/a/", sourcePath: "a.md", frontmatter: { title: "A" }, content: "", html: "<p>A</p>" },
      { path: "/b/", sourcePath: "b.md", frontmatter: { title: "B" }, content: "", html: "<p>B</p>" },
    ];

    const result = renderPage(pages[0], pages, templateDir, layout, makeOpts(templateDir));
    expect(result).toContain('<a href="/a/">A</a>');
    expect(result).toContain('<a href="/b/">B</a>');
  });

  it("excludes draft pages from pages list", () => {
    fs.writeFileSync(
      path.join(templateDir, "layout.hbs"),
      '<!DOCTYPE html>{{#each pages}}{{title}},{{/each}}</html>'
    );

    const layout = configureTemplateEngine(templateDir);
    const pages: Page[] = [
      { path: "/a/", sourcePath: "a.md", frontmatter: { title: "Published" }, content: "", html: "" },
      { path: "/b/", sourcePath: "b.md", frontmatter: { title: "Draft", draft: true }, content: "", html: "" },
    ];

    const result = renderPage(pages[0], pages, templateDir, layout, makeOpts(templateDir));
    expect(result).toContain("Published");
    expect(result).not.toContain("Draft");
  });
});

describe("buildTagMap", () => {
  it("groups pages by tags", () => {
    const pages: Page[] = [
      { path: "/a/", sourcePath: "a.md", frontmatter: { tags: ["js", "web"] }, content: "", html: "" },
      { path: "/b/", sourcePath: "b.md", frontmatter: { tags: ["css", "web"] }, content: "", html: "" },
      { path: "/c/", sourcePath: "c.md", frontmatter: { tags: ["js"] }, content: "", html: "" },
    ];

    const map = buildTagMap(pages);
    expect(map.get("js")?.length).toBe(2);
    expect(map.get("web")?.length).toBe(2);
    expect(map.get("css")?.length).toBe(1);
  });
});

describe("generateTagIndex", () => {
  let templateDir: string;

  beforeAll(() => {
    templateDir = fs.mkdtempSync(path.join(os.tmpdir(), "ss-tag-"));
    fs.writeFileSync(
      path.join(templateDir, "layout.hbs"),
      '<!DOCTYPE html><title>{{title}}</title>{{{body}}}'
    );
  });

  it("generates tag index with layout", () => {
    const layout = configureTemplateEngine(templateDir);
    const pages: Page[] = [
      { path: "/a/", sourcePath: "a.md", frontmatter: { title: "Post A" }, content: "", html: "" },
      { path: "/b/", sourcePath: "b.md", frontmatter: { title: "Post B" }, content: "", html: "" },
    ];

    const result = generateTagIndex("javascript", pages, layout, makeOpts(templateDir));
    expect(result).toContain("<!DOCTYPE html>");
    expect(result).toContain("<title>Tag: javascript</title>");
    expect(result).toContain('<a href="/a/">Post A</a>');
    expect(result).toContain('<a href="/b/">Post B</a>');
  });

  it("generates tag index without layout (fallback)", () => {
    const pages: Page[] = [
      { path: "/x/", sourcePath: "x.md", frontmatter: { title: "X" }, content: "", html: "" },
    ];

    const result = generateTagIndex("tag", pages, null, makeOpts(templateDir));
    expect(result).toContain("<!DOCTYPE html>");
    expect(result).toContain("Tag: tag");
    expect(result).toContain('<a href="/x/">X</a>');
  });
});

describe("markdown rendering", () => {
  beforeAll(() => {
    configureMarked();
  });

  it("converts markdown to HTML", () => {
    const html = markdownToHtml("# Hello\n\nThis is **bold**.");
    expect(html).toContain("<h1>Hello</h1>");
    expect(html).toContain("<strong>bold</strong>");
  });

  it("applies syntax highlighting to code blocks", () => {
    const html = markdownToHtml('```typescript\nconst x: number = 1;\n```');
    expect(html).toContain('<code class="hljs language-typescript">');
    expect(html).toContain("hljs");
  });

  it("handles unknown language without error", () => {
    const html = markdownToHtml('```fake\nabc\n```');
    expect(html).toContain("<pre><code>");
    expect(html).toContain("abc");
  });
});
