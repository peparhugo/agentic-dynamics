import { describe, it, expect } from "vitest";
import { execSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import os from "node:os";

function runCli(args: string): string {
  return execSync(
    `node --import tsx ${path.join(__dirname, "..", "src", "index.ts")} ${args}`,
    { encoding: "utf-8", cwd: __dirname }
  );
}

describe("CLI", () => {
  let tmpDir: string;

  function setupFixture() {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "ssg-cli-"));

    const source = path.join(tmpDir, "source");
    const templates = path.join(tmpDir, "templates");
    const output = path.join(tmpDir, "output");

    fs.mkdirSync(source, { recursive: true });
    fs.mkdirSync(path.join(templates, "partials"), { recursive: true });
    fs.mkdirSync(output, { recursive: true });

    fs.writeFileSync(
      path.join(source, "hello.md"),
      `---
title: Hello
date: 2024-01-01
tags:
  - greeting
---
Welcome to my site.`
    );

    fs.writeFileSync(
      path.join(source, "draft.md"),
      `---
title: Draft
date: 2024-06-01
tags:
  - secret
draft: true
---
This is a draft.`
    );

    fs.writeFileSync(
      path.join(source, "style.css"),
      "body { color: red; }"
    );

    fs.writeFileSync(
      path.join(templates, "layout.hbs"),
      `<html><head><title>{{site.title}}</title></head><body>{{{body}}}</body></html>`
    );

    fs.writeFileSync(
      path.join(templates, "page.hbs"),
      `<h1>{{page.title}}</h1><div>{{{page.content}}}</div>`
    );

    fs.writeFileSync(
      path.join(templates, "listing.hbs"),
      `<h1>Posts</h1>{{#each pages}}<a href="/{{slug}}/">{{title}}</a>{{/each}}`
    );

    fs.writeFileSync(
      path.join(templates, "tag.hbs"),
      `<h1>Tag: {{tag.tag}}</h1>{{#each pages}}<a href="/{{slug}}/">{{title}}</a>{{/each}}`
    );

    return { source, templates, output, tmpDir };
  }

  it("builds a static site from flags", () => {
    const { source, templates, output } = setupFixture();

    runCli(
      `--source "${source}" --templates "${templates}" --output "${output}" --site-title "CLI Test" --base-url "https://example.com"`
    );

    expect(fs.existsSync(path.join(output, "hello", "index.html"))).toBe(true);
  });

  it("renders frontmatter title in output", () => {
    const { source, templates, output } = setupFixture();

    runCli(
      `--source "${source}" --templates "${templates}" --output "${output}"`
    );

    const html = fs.readFileSync(
      path.join(output, "hello", "index.html"),
      "utf-8"
    );
    expect(html).toContain("<h1>Hello</h1>");
  });

  it("generates listing page at root", () => {
    const { source, templates, output } = setupFixture();

    runCli(
      `--source "${source}" --templates "${templates}" --output "${output}"`
    );

    const html = fs.readFileSync(path.join(output, "index.html"), "utf-8");
    expect(html).toContain("Posts");
    expect(html).toContain('href="/hello/"');
  });

  it("generates tag index pages", () => {
    const { source, templates, output } = setupFixture();

    runCli(
      `--source "${source}" --templates "${templates}" --output "${output}"`
    );

    const html = fs.readFileSync(
      path.join(output, "tags", "greeting", "index.html"),
      "utf-8"
    );
    expect(html).toContain("Tag: greeting");
    expect(html).toContain('href="/hello/"');
  });

  it("generates RSS feed", () => {
    const { source, templates, output } = setupFixture();

    runCli(
      `--source "${source}" --templates "${templates}" --output "${output}"`
    );

    const rss = fs.readFileSync(path.join(output, "feed.xml"), "utf-8");
    expect(rss).toContain("<?xml");
    expect(rss).toContain("<rss");
    expect(rss).toContain("<title>Hello</title>");
  });

  it("filters out draft posts in production build", () => {
    const { source, templates, output } = setupFixture();

    runCli(
      `--source "${source}" --templates "${templates}" --output "${output}"`
    );

    expect(fs.existsSync(path.join(output, "draft", "index.html"))).toBe(false);
  });

  it("includes draft posts with --dev flag", () => {
    const { source, templates, output } = setupFixture();

    runCli(
      `--source "${source}" --templates "${templates}" --output "${output}" --dev --port 13999`
    );

    expect(
      fs.existsSync(path.join(output, "draft", "index.html"))
    ).toBe(true);
  });

  it("copies non-markdown assets from source", () => {
    const { source, templates, output } = setupFixture();

    runCli(
      `--source "${source}" --templates "${templates}" --output "${output}"`
    );

    expect(fs.existsSync(path.join(output, "style.css"))).toBe(true);
    const css = fs.readFileSync(path.join(output, "style.css"), "utf-8");
    expect(css).toContain("red");
  });

  it("wraps pages with layout template", () => {
    const { source, templates, output } = setupFixture();

    runCli(
      `--source "${source}" --templates "${templates}" --output "${output}" --site-title "My Blog"`
    );

    const html = fs.readFileSync(
      path.join(output, "hello", "index.html"),
      "utf-8"
    );
    expect(html).toContain("<html>");
    expect(html).toContain("<title>My Blog</title>");
  });

  it("accepts --author flag", () => {
    const { source, templates, output } = setupFixture();

    runCli(
      `--source "${source}" --templates "${templates}" --output "${output}" --author "Test Author" --base-url "https://example.com"`
    );

    const rss = fs.readFileSync(path.join(output, "feed.xml"), "utf-8");
    expect(rss).toContain("Test Author");
  });

  it("logs build output message", () => {
    const { source, templates, output } = setupFixture();

    const stdout = runCli(
      `--source "${source}" --templates "${templates}" --output "${output}"`
    );
    expect(stdout).toContain("Site built to");
  });
});
