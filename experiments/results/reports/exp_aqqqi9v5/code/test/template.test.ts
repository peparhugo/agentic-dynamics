import { describe, it, expect, beforeAll, afterAll } from "vitest";
import fs from "node:fs/promises";
import path from "node:path";
import os from "node:os";
import { compileTemplates, renderPage, renderTagPage, renderIndex } from "../src/template.js";
import type { Page, SiteConfig, TagIndex } from "../src/types.js";

const config: SiteConfig = {
  title: "Test Site",
  description: "A test site",
  baseUrl: "http://localhost:8080",
  sourceDir: "/src",
  templateDir: "",
  outputDir: "/out",
};

function makePage(overrides: Partial<Page> = {}): Page {
  return {
    frontmatter: { title: "Test Post", date: "2024-01-01", tags: ["test"] },
    content: "Content",
    html: "<p>Content</p>",
    slug: "test-post",
    sourcePath: "/src/test-post.md",
    outputPath: "/out/test-post.html",
    isDraft: false,
    ...overrides,
  };
}

describe("template", () => {
  let tmpDir: string;

  beforeAll(async () => {
    tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), "ssg-tmpl-"));
    config.templateDir = tmpDir;

    await fs.writeFile(
      path.join(tmpDir, "layout.hbs"),
      `<html><head><title>{{title}}</title></head><body><h1>{{title}}</h1>{{{content}}}<footer>Tags: {{#each tags}}{{this}} {{/each}}</footer></body></html>`,
    );
    await fs.writeFile(
      path.join(tmpDir, "index.hbs"),
      `<html><body><h1>{{config.title}}</h1><ul>{{#each pages}}<li><a href="{{slug}}.html">{{frontmatter.title}}</a></li>{{/each}}</ul></body></html>`,
    );
    await fs.writeFile(
      path.join(tmpDir, "tag.hbs"),
      `<html><body><h1>Tag: {{tag}}</h1><ul>{{#each pages}}<li>{{frontmatter.title}}</li>{{/each}}</ul></body></html>`,
    );
    await fs.writeFile(
      path.join(tmpDir, "_header.hbs"),
      `<header>{{config.title}}</header>`,
    );
    await fs.writeFile(
      path.join(tmpDir, "_footer.hbs"),
      `<footer>&copy; {{config.title}}</footer>`,
    );
  });

  afterAll(async () => {
    await fs.rm(tmpDir, { recursive: true, force: true });
  });

  it("compiles templates from a directory", async () => {
    const { templates, partials } = await compileTemplates(tmpDir);
    expect(templates.has("layout")).toBe(true);
    expect(templates.has("index")).toBe(true);
    expect(templates.has("tag")).toBe(true);
    expect(partials.has("header")).toBe(true);
    expect(partials.has("footer")).toBe(true);
  });

  it("renders a page with layout template", async () => {
    const { templates } = await compileTemplates(tmpDir);
    const page = makePage();
    const html = renderPage(page, templates.get("layout")!, [page], config);
    expect(html).toContain("<h1>Test Post</h1>");
    expect(html).toContain("<p>Content</p>");
    expect(html).toContain("Tags:");
    expect(html).toContain("test");
  });

  it("renders an index page listing all pages", async () => {
    const { templates } = await compileTemplates(tmpDir);
    const pages = [
      makePage({ slug: "post-a", frontmatter: { title: "Post A" } }),
      makePage({ slug: "post-b", frontmatter: { title: "Post B" } }),
    ];
    const html = renderIndex(pages, templates.get("index")!, config);
    expect(html).toContain("Test Site");
    expect(html).toContain("post-a.html");
    expect(html).toContain("Post A");
    expect(html).toContain("Post B");
  });

  it("renders a tag page", async () => {
    const { templates } = await compileTemplates(tmpDir);
    const pages = [makePage({ slug: "p1" }), makePage({ slug: "p2" })];
    const tagIndex: TagIndex = { tag: "typescript", pages };
    const html = renderTagPage(tagIndex, templates.get("tag")!, config);
    expect(html).toContain("Tag: typescript");
    expect(html).toContain("Test Post");
  });

  it("partials are registered and available", async () => {
    const { templates } = await compileTemplates(tmpDir);

    const layoutWithPartial = `{{> header}}{{title}}{{> footer}}`;
    const Handlebars = await import("handlebars");
    const compiled = Handlebars.default.compile(layoutWithPartial);
    const html = compiled({ title: "Page", config });
    expect(html).toContain("<header>Test Site</header>");
    expect(html).toContain("Page");
    expect(html).toContain("<footer>&copy; Test Site</footer>");
  });

  it("sorts pages by date descending in renderIndex", async () => {
    const { templates } = await compileTemplates(tmpDir);
    const pages = [
      makePage({ frontmatter: { title: "Old", date: "2023-01-01", tags: [] } }),
      makePage({ frontmatter: { title: "New", date: "2025-01-01", tags: [] } }),
    ];
    const html = renderIndex(pages, templates.get("index")!, config);
    const newIdx = html.indexOf("New");
    const oldIdx = html.indexOf("Old");
    expect(newIdx).toBeLessThan(oldIdx);
  });

  it("excludes drafts from index", async () => {
    const { templates } = await compileTemplates(tmpDir);
    const pages = [
      makePage({
        frontmatter: { title: "Drafty", tags: [] },
        isDraft: true,
        slug: "draft",
      }),
      makePage({
        frontmatter: { title: "Published", tags: [] },
        isDraft: false,
        slug: "pub",
      }),
    ];
    const html = renderIndex(pages, templates.get("index")!, config);
    expect(html).not.toContain("draft");
    expect(html).toContain("pub");
  });
});
