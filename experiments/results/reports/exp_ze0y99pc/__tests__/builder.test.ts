import { describe, it, expect, beforeEach } from "vitest";
import { buildSite } from "../src/lib/builder";
import { buildPosts, buildTagIndexes } from "../src/lib/builder";
import { parseMarkdownFile, collectPosts } from "../src/lib/parser";
import * as fs from "fs";
import * as path from "path";
import * as os from "os";

describe("buildTagIndexes", () => {
  it("groups posts by tag", () => {
    const posts = [
      {
        slug: "a",
        sourcePath: "/a.md",
        frontmatter: { title: "A", tags: ["ts", "web"] },
        body: "",
        html: "",
        url: "/a.html",
      },
      {
        slug: "b",
        sourcePath: "/b.md",
        frontmatter: { title: "B", tags: ["ts"] },
        body: "",
        html: "",
        url: "/b.html",
      },
      {
        slug: "c",
        sourcePath: "/c.md",
        frontmatter: { title: "C", tags: ["web"] },
        body: "",
        html: "",
        url: "/c.html",
      },
    ];

    const indexes = buildTagIndexes(posts);
    expect(indexes).toHaveLength(2);

    const tsIdx = indexes.find((i) => i.tag === "ts")!;
    expect(tsIdx.posts).toHaveLength(2);

    const webIdx = indexes.find((i) => i.tag === "web")!;
    expect(webIdx.posts).toHaveLength(2);
  });

  it("excludes draft posts from tag indexes", () => {
    const posts = [
      {
        slug: "pub",
        sourcePath: "/pub.md",
        frontmatter: { title: "Pub", tags: ["ts"] },
        body: "",
        html: "",
        url: "/pub.html",
      },
      {
        slug: "draft",
        sourcePath: "/draft.md",
        frontmatter: { title: "Draft", tags: ["ts"], draft: true },
        body: "",
        html: "",
        url: "/draft.html",
      },
    ];

    const indexes = buildTagIndexes(posts);
    const tsIdx = indexes.find((i) => i.tag === "ts")!;
    expect(tsIdx.posts).toHaveLength(1);
    expect(tsIdx.posts[0].slug).toBe("pub");
  });

  it("returns empty array for posts without tags", () => {
    const posts = [
      {
        slug: "notag",
        sourcePath: "/notag.md",
        frontmatter: { title: "No Tags" },
        body: "",
        html: "",
        url: "/notag.html",
      },
    ];

    const indexes = buildTagIndexes(posts);
    expect(indexes).toHaveLength(0);
  });
});

describe("buildPosts", () => {
  it("converts markdown body to HTML", () => {
    const posts = [
      {
        slug: "test",
        sourcePath: "/test.md",
        frontmatter: { title: "Test" },
        body: "# Hello\n\nWorld",
        html: "",
        url: "/test.html",
      },
    ];

    buildPosts(posts);
    expect(posts[0].html).toContain("<h1");
    expect(posts[0].html).toContain("<p>World</p>");
  });
});

describe("buildSite (integration)", () => {
  let tmpDir: string;
  let sourceDir: string;
  let templateDir: string;
  let outputDir: string;

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "statick-int-"));
    sourceDir = path.join(tmpDir, "content");
    templateDir = path.join(tmpDir, "templates");
    outputDir = path.join(tmpDir, "output");

    fs.mkdirSync(sourceDir, { recursive: true });
    fs.mkdirSync(templateDir, { recursive: true });

    fs.writeFileSync(
      path.join(sourceDir, "config.yaml"),
      "title: Test Site\ndescription: A test site\nurl: https://test.com\n"
    );

    fs.writeFileSync(
      path.join(sourceDir, "hello.md"),
      `---
title: Hello World
date: 2024-06-01
tags:
  - blog
  - intro
---

# Hello

This is a test post.`
    );

    fs.writeFileSync(
      path.join(sourceDir, "draft.md"),
      `---
title: Secret Draft
date: 2024-06-02
draft: true
---

Should not appear.`
    );

    fs.writeFileSync(
      path.join(templateDir, "index.hbs"),
      `{{#each posts}}<h2>{{frontmatter.title}}</h2>{{/each}}`
    );

    fs.writeFileSync(
      path.join(templateDir, "post.hbs"),
      `<h1>{{post.frontmatter.title}}</h1>{{{post.html}}}`
    );

    fs.writeFileSync(
      path.join(templateDir, "tag.hbs"),
      `<h1>Tag: {{tag.tag}}</h1>{{#each tag.posts}}<a href="{{url}}">{{frontmatter.title}}</a>{{/each}}`
    );

    fs.writeFileSync(
      path.join(templateDir, "tags-index.hbs"),
      `{{#each tags}}<a href="{{url}}">{{tag}}</a>{{/each}}`
    );

    fs.writeFileSync(
      path.join(templateDir, "layouts", "default.hbs"),
      `<html><body>{{{content}}}</body></html>`,
      { recursive: true }
    );
  });

  it("generates index.html with published posts", () => {
    buildSite(sourceDir, templateDir, outputDir);

    const indexPath = path.join(outputDir, "index.html");
    expect(fs.existsSync(indexPath)).toBe(true);

    const indexContent = fs.readFileSync(indexPath, "utf-8");
    expect(indexContent).toContain("Hello World");
    expect(indexContent).not.toContain("Secret Draft");
  });

  it("generates post pages", () => {
    buildSite(sourceDir, templateDir, outputDir);

    const postPath = path.join(outputDir, "hello-world.html");
    expect(fs.existsSync(postPath)).toBe(true);

    const postContent = fs.readFileSync(postPath, "utf-8");
    expect(postContent).toContain("<h1>Hello World</h1>");
    expect(postContent).toContain("<html>");
  });

  it("does not generate draft post pages", () => {
    buildSite(sourceDir, templateDir, outputDir);

    const draftPath = path.join(outputDir, "secret-draft.html");
    expect(fs.existsSync(draftPath)).toBe(false);
  });

  it("generates tag index pages", () => {
    buildSite(sourceDir, templateDir, outputDir);

    const tagPath = path.join(outputDir, "tags", "blog.html");
    expect(fs.existsSync(tagPath)).toBe(true);

    const tagContent = fs.readFileSync(tagPath, "utf-8");
    expect(tagContent).toContain("Tag: blog");
    expect(tagContent).toContain("Hello World");
  });

  it("generates tags overview page", () => {
    buildSite(sourceDir, templateDir, outputDir);

    const tagsPath = path.join(outputDir, "tags.html");
    expect(fs.existsSync(tagsPath)).toBe(true);

    const tagsContent = fs.readFileSync(tagsPath, "utf-8");
    expect(tagsContent).toContain("blog");
    expect(tagsContent).toContain("intro");
  });

  it("generates RSS feed", () => {
    buildSite(sourceDir, templateDir, outputDir);

    const rssPath = path.join(outputDir, "rss.xml");
    expect(fs.existsSync(rssPath)).toBe(true);

    const rssContent = fs.readFileSync(rssPath, "utf-8");
    expect(rssContent).toContain("<rss");
    expect(rssContent).toContain("Hello World");
    expect(rssContent).not.toContain("Secret Draft");
  });
});
