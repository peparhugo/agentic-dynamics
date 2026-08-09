import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { runCli } from "../src/cli";
import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import http from "node:http";

let tempDir: string;
let sourceDir: string;
let templateDir: string;
let outputDir: string;

function setupDirs() {
  tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "statik-cli-"));
  sourceDir = path.join(tempDir, "content");
  templateDir = path.join(tempDir, "templates");
  outputDir = path.join(tempDir, "dist");

  fs.mkdirSync(sourceDir);
  fs.mkdirSync(path.join(templateDir, "partials"), { recursive: true });

  fs.writeFileSync(
    path.join(templateDir, "index.hbs"),
    `<!doctype html><html><body><h1>{{site.title}}</h1><ul>{{#each posts}}<li>{{title}}</li>{{/each}}</ul></body></html>`
  );
  fs.writeFileSync(
    path.join(templateDir, "post.hbs"),
    `<!doctype html><html><body><article><h1>{{post.title}}</h1>{{{post.content}}}</article></body></html>`
  );
  fs.writeFileSync(
    path.join(templateDir, "tag.hbs"),
    `<!doctype html><html><body><h1>Tag</h1></body></html>`
  );
  fs.writeFileSync(
    path.join(templateDir, "tags-index.hbs"),
    `<!doctype html><html><body><h1>Tags</h1></body></html>`
  );

  fs.writeFileSync(
    path.join(sourceDir, "hello.md"),
    `---\ntitle: Hello\ndate: 2024-01-01\ntags: [js]\n---\n# Hello`
  );
}

describe("CLI", () => {
  beforeEach(() => setupDirs());

  afterEach(() => {
    if (fs.existsSync(tempDir)) fs.rmSync(tempDir, { recursive: true });
  });

  it("builds with short flags -s -t -o", () => {
    runCli([
      "node",
      "statik",
      "-s",
      sourceDir,
      "-t",
      templateDir,
      "-o",
      outputDir,
    ]);

    const indexPath = path.join(outputDir, "index.html");
    expect(fs.existsSync(indexPath)).toBe(true);

    const content = fs.readFileSync(indexPath, "utf-8");
    expect(content).toContain("My Site");
    expect(content).toContain("Hello");
  });

  it("builds with long flags --source --templates --output", () => {
    runCli([
      "node",
      "statik",
      "--source",
      sourceDir,
      "--templates",
      templateDir,
      "--output",
      outputDir,
      "--title",
      "Custom Title",
      "--author",
      "Jane",
    ]);

    const content = fs.readFileSync(
      path.join(outputDir, "index.html"),
      "utf-8"
    );
    expect(content).toContain("Custom Title");
  });

  it("creates directory structure output", () => {
    runCli([
      "node",
      "statik",
      "-s",
      sourceDir,
      "-t",
      templateDir,
      "-o",
      outputDir,
    ]);

    expect(fs.existsSync(path.join(outputDir, "index.html"))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, "posts", "hello", "index.html"))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, "tags", "js", "index.html"))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, "tags", "index.html"))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, "feed.xml"))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, "site.json"))).toBe(true);
  });

  it("uses default option values", () => {
    const defaultOut = path.join(tempDir, "dist-default");
    runCli([
      "node",
      "statik",
      "-s",
      sourceDir,
      "-t",
      templateDir,
      "-o",
      defaultOut,
    ]);

    expect(fs.existsSync(path.join(defaultOut, "index.html"))).toBe(true);
    const content = fs.readFileSync(
      path.join(defaultOut, "index.html"),
      "utf-8"
    );
    expect(content).toContain("My Site");
  });
});
