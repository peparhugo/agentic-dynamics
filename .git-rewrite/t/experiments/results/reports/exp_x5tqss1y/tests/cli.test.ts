import { describe, it, expect, beforeEach, afterEach } from "vitest";
import * as fs from "node:fs";
import * as path from "node:path";
import * as os from "node:os";
import { execSync } from "node:child_process";

describe("cli integration", () => {
  let tmpDir: string;
  let sourceDir: string;
  let templatesDir: string;
  let outputDir: string;

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "ssg-cli-"));
    sourceDir = path.join(tmpDir, "content");
    templatesDir = path.join(tmpDir, "templates");
    outputDir = path.join(tmpDir, "out");

    fs.mkdirSync(sourceDir, { recursive: true });
    fs.mkdirSync(path.join(templatesDir, "layouts"), { recursive: true });
    fs.mkdirSync(path.join(templatesDir, "partials"), { recursive: true });

    fs.writeFileSync(path.join(sourceDir, "post.md"), `---
title: Test Post
date: 2024-06-01
tags: [js]
draft: false
---
# Hello

Some content.

\`\`\`js
console.log("test");
\`\`\`
`);

    fs.writeFileSync(path.join(templatesDir, "page.hbs"), `{{#layout "base"}}
<h1>{{page.frontmatter.title}}</h1>
<div>{{{page.html}}}</div>
{{/layout}}`);

    fs.writeFileSync(path.join(templatesDir, "index.hbs"), `{{#layout "base"}}
<h1>{{site.title}}</h1>
<ul>
{{#each pages}}<li><a href="/{{slug}}.html">{{frontmatter.title}}</a></li>{{/each}}
</ul>
{{/layout}}`);

    fs.writeFileSync(path.join(templatesDir, "tag.hbs"), `{{#layout "base"}}
<h1>Tag: {{currentTag}}</h1>
{{/layout}}`);

    fs.writeFileSync(path.join(templatesDir, "layouts", "base.hbs"), `<!DOCTYPE html>
<html>
<head><title>{{site.title}}</title></head>
<body>{{{body}}}</body>
</html>`);
  });

  afterEach(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  function runCli(args: string): void {
    const cliPath = path.resolve("dist/cli.js");
    execSync(`node ${cliPath} ${args}`, { cwd: tmpDir, stdio: "pipe" });
  }

  it("--help prints usage", () => {
    const cliPath = path.resolve("dist/cli.js");
    const out = execSync(`node ${cliPath} --help`, { stdio: "pipe" }).toString();
    expect(out).toContain("--source");
    expect(out).toContain("--templates");
    expect(out).toContain("--output");
    expect(out).toContain("--serve");
  });

  it("builds a site from source and templates", () => {
    runCli(`-s ${sourceDir} -t ${templatesDir} -o ${outputDir} --site-title "My Site"`);

    expect(fs.existsSync(path.join(outputDir, "post.html"))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, "index.html"))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, "rss.xml"))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, "style.css"))).toBe(true);

    const postHtml = fs.readFileSync(path.join(outputDir, "post.html"), "utf-8");
    expect(postHtml).toContain("<h1>Test Post</h1>");
    expect(postHtml).toContain("<!DOCTYPE html>");

    const indexHtml = fs.readFileSync(path.join(outputDir, "index.html"), "utf-8");
    expect(indexHtml).toContain('<a href="/post.html">Test Post</a>');
  });

  it("generates tag pages", () => {
    runCli(`-s ${sourceDir} -t ${templatesDir} -o ${outputDir} --site-title "Tagged"`);
    const tagPage = path.join(outputDir, "tags", "js.html");
    expect(fs.existsSync(tagPage)).toBe(true);
    const html = fs.readFileSync(tagPage, "utf-8");
    expect(html).toContain("Tag: js");
  });

  it("generates RSS feed", () => {
    runCli(`-s ${sourceDir} -t ${templatesDir} -o ${outputDir} --site-title "RSS Site" --site-url "https://rss.example.com"`);
    const rss = fs.readFileSync(path.join(outputDir, "rss.xml"), "utf-8");
    expect(rss).toContain("<title>Test Post</title>");
    expect(rss).toContain("https://rss.example.com");
  });

  it("respects --site-title, --site-url, --site-description", () => {
    runCli(
      `-s ${sourceDir} -t ${templatesDir} -o ${outputDir} --site-title "Custom Title" --site-url "https://custom.com" --site-description "Custom desc"`
    );
    const indexHtml = fs.readFileSync(path.join(outputDir, "index.html"), "utf-8");
    expect(indexHtml).toContain("<h1>Custom Title</h1>");
    expect(indexHtml).toContain("<title>Custom Title</title>");

    const rss = fs.readFileSync(path.join(outputDir, "rss.xml"), "utf-8");
    expect(rss).toContain("Custom Title");
    expect(rss).toContain("https://custom.com");
    expect(rss).toContain("Custom desc");
  });

  it("rejects missing required options", () => {
    const cliPath = path.resolve("dist/cli.js");
    expect(() =>
      execSync(`node ${cliPath} -s ${sourceDir}`, { stdio: "pipe", cwd: tmpDir })
    ).toThrow();
  });
});
