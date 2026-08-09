import { describe, it, expect } from "vitest";
import { execSync } from "child_process";
import fs from "fs";
import path from "path";
import os from "os";

const CLI = path.resolve(__dirname, "..", "node_modules", ".bin", "tsx");
const ENTRY = path.resolve(__dirname, "..", "src", "index.ts");

function run(args: string): string {
  try {
    return execSync(`npx tsx ${ENTRY} ${args}`, {
      cwd: path.resolve(__dirname, ".."),
      stdio: "pipe",
      encoding: "utf-8",
    });
  } catch (e: any) {
    // Commander exits with process.exit which throws; capture stderr
    if (e.stdout) return e.stdout.toString();
    if (e.stderr) return e.stderr.toString();
    throw e;
  }
}

describe("CLI flags", () => {
  let tmpDir: string;

  function setupFixture() {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "ss-cli-"));

    // Source: content/
    fs.mkdirSync(path.join(tmpDir, "content"), { recursive: true });
    fs.writeFileSync(
      path.join(tmpDir, "content", "index.md"),
      `---
title: Home
date: 2024-01-01
---
# Welcome

Hello world.`
    );

    fs.writeFileSync(
      path.join(tmpDir, "content", "about.md"),
      `---
title: About
date: 2024-01-02
---
## About Us

We are us.`
    );

    fs.writeFileSync(
      path.join(tmpDir, "content", "draft.md"),
      `---
title: Draft Post
draft: true
---
# Not ready`
    );

    // Templates: templates/
    fs.mkdirSync(path.join(tmpDir, "templates"), { recursive: true });
    fs.writeFileSync(
      path.join(tmpDir, "templates", "layout.hbs"),
      '<!DOCTYPE html><html><head><title>{{title}}</title></head><body><h1>{{title}}</h1>{{{body}}}</body></html>'
    );

    return tmpDir;
  }

  it("builds site with default directories", () => {
    const dir = setupFixture();
    const result = run(`build -s ${path.join(dir, "content")} -t ${path.join(dir, "templates")} -o ${path.join(dir, "_site")} --site-name "My Blog" --site-url "https://example.com"`);
    expect(fs.existsSync(path.join(dir, "_site", "index.html"))).toBe(true);
    expect(fs.existsSync(path.join(dir, "_site", "about", "index.html"))).toBe(true);
    expect(fs.existsSync(path.join(dir, "_site", "feed.xml"))).toBe(true);

    const indexHtml = fs.readFileSync(path.join(dir, "_site", "index.html"), "utf-8");
    expect(indexHtml).toContain("<!DOCTYPE html>");
    expect(indexHtml).toContain("<title>Home</title>");
    expect(indexHtml).toContain("<h1>Welcome</h1>");

    // Draft should not be output
    expect(fs.existsSync(path.join(dir, "_site", "draft", "index.html"))).toBe(false);

    fs.rmSync(dir, { recursive: true });
  });

  it("respects --site-name and --site-url flags", () => {
    const dir = setupFixture();
    run(`build -s ${path.join(dir, "content")} -t ${path.join(dir, "templates")} -o ${path.join(dir, "_site")} --site-name "Custom Name" --site-url "https://custom.url"`);

    const feed = fs.readFileSync(path.join(dir, "_site", "feed.xml"), "utf-8");
    expect(feed).toContain("Custom Name");
    expect(feed).toContain("https://custom.url");

    fs.rmSync(dir, { recursive: true });
  });

  it("generates RSS feed with dated posts", () => {
    const dir = setupFixture();
    run(`build -s ${path.join(dir, "content")} -t ${path.join(dir, "templates")} -o ${path.join(dir, "_site")} --site-url "https://blog.example.com"`);

    const feed = fs.readFileSync(path.join(dir, "_site", "feed.xml"), "utf-8");
    expect(feed).toContain("<rss");
    expect(feed).toContain("<item>");
    expect(feed).toContain("<title>Home</title>");
    expect(feed).toContain("<title>About</title>");
    expect(feed).not.toContain("Draft Post"); // drafts excluded

    fs.rmSync(dir, { recursive: true });
  });

  it("skips draft pages in output", () => {
    const dir = setupFixture();
    run(`build -s ${path.join(dir, "content")} -t ${path.join(dir, "templates")} -o ${path.join(dir, "_site")} --site-url "https://example.com"`);

    const draftsDir = path.join(dir, "_site", "draft");
    expect(fs.existsSync(draftsDir)).toBe(false);

    fs.rmSync(dir, { recursive: true });
  });

  it("generates tag index pages", () => {
    const dir = setupFixture();
    // Add a tagged page
    fs.writeFileSync(
      path.join(dir, "content", "js-post.md"),
      `---
title: JavaScript Post
date: 2024-01-03
tags:
  - javascript
  - web
---
# JS is cool`
    );

    run(`build -s ${path.join(dir, "content")} -t ${path.join(dir, "templates")} -o ${path.join(dir, "_site")} --site-url "https://example.com"`);

    expect(fs.existsSync(path.join(dir, "_site", "tags", "javascript", "index.html"))).toBe(true);
    expect(fs.existsSync(path.join(dir, "_site", "tags", "web", "index.html"))).toBe(true);

    const tagPage = fs.readFileSync(path.join(dir, "_site", "tags", "javascript", "index.html"), "utf-8");
    expect(tagPage).toContain("Tag: javascript");
    expect(tagPage).toContain("JavaScript Post");

    fs.rmSync(dir, { recursive: true });
  });

  it("handles Handlebars partials", () => {
    const dir = setupFixture();

    // Add partial
    fs.mkdirSync(path.join(dir, "templates", "partials"), { recursive: true });
    fs.writeFileSync(path.join(dir, "templates", "partials", "nav.hbs"), '<nav>Partials work!</nav>');

    // Update layout to use partial
    fs.writeFileSync(
      path.join(dir, "templates", "layout.hbs"),
      '<!DOCTYPE html>{{> nav}}<h1>{{title}}</h1>{{{body}}}'
    );

    run(`build -s ${path.join(dir, "content")} -t ${path.join(dir, "templates")} -o ${path.join(dir, "_site")} --site-url "https://example.com"`);

    const indexHtml = fs.readFileSync(path.join(dir, "_site", "index.html"), "utf-8");
    expect(indexHtml).toContain("<nav>Partials work!</nav>");

    fs.rmSync(dir, { recursive: true });
  });

  it("page-specific template via frontmatter.template", () => {
    const dir = setupFixture();

    fs.writeFileSync(
      path.join(dir, "templates", "custom.hbs"),
      '<article class="custom">{{{content}}}</article>'
    );

    fs.writeFileSync(
      path.join(dir, "content", "special.md"),
      `---
title: Special
template: custom.hbs
---
Custom template content.`
    );

    run(`build -s ${path.join(dir, "content")} -t ${path.join(dir, "templates")} -o ${path.join(dir, "_site")} --site-url "https://example.com"`);

    const html = fs.readFileSync(path.join(dir, "_site", "special", "index.html"), "utf-8");
    expect(html).toContain('<article class="custom">');

    fs.rmSync(dir, { recursive: true });
  });
});
