import { describe, it, before, after } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import os from "node:os";
import Handlebars from "handlebars";
import { loadTemplates, applyLayout, type Templates } from "../src/render.js";

const dummyTemplate = Handlebars.compile("");

function mockTemplates(overrides: Partial<Templates> = {}): Templates {
  return {
    layout: null,
    post: dummyTemplate,
    index: dummyTemplate,
    tag: dummyTemplate,
    rss: null,
    reloadScript: "",
    ...overrides,
  };
}

describe("loadTemplates", () => {
  let tmpDir: string;

  before(async () => {
    tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), "ssg-tpl-"));
    await fs.writeFile(
      path.join(tmpDir, "post.hbs"),
      `<article>{{frontmatter.title}}: {{{html}}}</article>`
    );
    await fs.writeFile(
      path.join(tmpDir, "index.hbs"),
      `<ul>{{#each posts}}<li>{{frontmatter.title}}</li>{{/each}}</ul>`
    );
    await fs.writeFile(
      path.join(tmpDir, "tag.hbs"),
      `<h1>{{tag}}</h1>`
    );
    await fs.writeFile(
      path.join(tmpDir, "layout.hbs"),
      `<html><body>{{{body}}}</body></html>`
    );
    await fs.mkdir(path.join(tmpDir, "partials"));
    await fs.writeFile(
      path.join(tmpDir, "partials", "header.hbs"),
      `<header>Site Header</header>`
    );
  });

  after(async () => {
    await fs.rm(tmpDir, { recursive: true, force: true });
  });

  it("loads post, index, tag, and optional layout templates", async () => {
    const tpl = await loadTemplates(tmpDir);
    assert.ok(tpl.post);
    assert.ok(tpl.index);
    assert.ok(tpl.tag);
    assert.ok(tpl.layout);
    assert.equal(tpl.rss, null);
  });

  it("registers partials from partials/ directory", async () => {
    await loadTemplates(tmpDir);
    const tpl = Handlebars.compile("{{> header}}");
    const result = tpl({});
    assert.ok(result.includes("Site Header"));
  });
});

describe("applyLayout", () => {
  it("wraps body with layout when layout template exists", async () => {
    const tpl = await loadTemplates(path.join(import.meta.dirname ?? ".", "fixtures", "templates"));
    const result = applyLayout(tpl, "<p>Hello</p>", { title: "Test" });
    assert.ok(result.includes("<!DOCTYPE html>"));
    assert.ok(result.includes("<p>Hello</p>"));
    assert.ok(result.includes("<title>Test"));
  });

  it("generates default HTML wrapper when no layout template", () => {
    const result = applyLayout(mockTemplates(), "<p>Hello</p>", { title: "Test" });
    assert.ok(result.includes("<!DOCTYPE html>"));
    assert.ok(result.includes("<p>Hello</p>"));
    assert.ok(result.includes("<title>Test</title>"));
  });

  it("injects reload script when available", () => {
    const result = applyLayout(
      mockTemplates({ reloadScript: "console.log('reload');" }),
      "<p>Hello</p>",
      { title: "Test" }
    );
    assert.ok(result.includes("console.log('reload')"));
  });
});

describe("template rendering with data", () => {
  let tmpDir: string;

  before(async () => {
    tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), "ssg-tpl2-"));
    await fs.writeFile(
      path.join(tmpDir, "post.hbs"),
      `<article><h1>{{frontmatter.title}}</h1>{{#if frontmatter.date}}<time>{{formatDate frontmatter.date}}</time>{{/if}}{{{html}}}</article>`
    );
    await fs.writeFile(
      path.join(tmpDir, "index.hbs"),
      `{{#each posts}}<p>{{frontmatter.title}}</p>{{/each}}`
    );
    await fs.writeFile(path.join(tmpDir, "tag.hbs"), `<h1>{{tag}}</h1>`);
  });

  after(async () => {
    await fs.rm(tmpDir, { recursive: true, force: true });
  });

  it("renders post template with frontmatter and HTML content", async () => {
    const tpl = await loadTemplates(tmpDir);
    const ctx = {
      frontmatter: { title: "My Post", date: "2025-03-01" },
      html: "<p>Body</p>",
    };
    const result = tpl.post(ctx, { allowProtoPropertiesByDefault: true });
    assert.ok(result.includes("My Post"));
    assert.ok(result.includes("2025-03-01"));
    assert.ok(result.includes("<p>Body</p>"));
  });

  it("renders index template with posts array", async () => {
    const tpl = await loadTemplates(tmpDir);
    const ctx = {
      posts: [
        { frontmatter: { title: "Post A" } },
        { frontmatter: { title: "Post B" } },
      ],
    };
    const result = tpl.index(ctx, { allowProtoPropertiesByDefault: true });
    assert.ok(result.includes("Post A"));
    assert.ok(result.includes("Post B"));
  });

  it("renders tag template with tag name and posts", async () => {
    const tpl = await loadTemplates(tmpDir);
    const ctx = { tag: "javascript" };
    const result = tpl.tag(ctx, { allowProtoPropertiesByDefault: true });
    assert.ok(result.includes("javascript"));
  });
});
