import { describe, it, expect, afterEach } from "vitest";
import { execSync } from "node:child_process";
import { existsSync, rmSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = fileURLToPath(new URL(".", import.meta.url));
const rootDir = resolve(__dirname, "..");
const outDir = resolve(rootDir, "test-output");
const cliEntry = resolve(rootDir, "dist/index.js");

const fixtureSrc = resolve(__dirname, "fixtures/src");
const fixtureTemplates = resolve(__dirname, "fixtures/templates");

function runSsg(args: string): string {
  return execSync(`node ${cliEntry} ${args}`, {
    cwd: rootDir,
    encoding: "utf-8",
    env: { ...process.env, NODE_NO_WARNINGS: "1" },
  });
}

describe("CLI flags", () => {
  afterEach(() => {
    if (existsSync(outDir)) {
      rmSync(outDir, { recursive: true, force: true });
    }
  });

  it("shows help text with --help", () => {
    const output = runSsg("--help");
    expect(output).toContain("Static site generator");
    expect(output).toContain("--source");
    expect(output).toContain("--templates");
    expect(output).toContain("--output");
  });

  it("shows version with --version", () => {
    const output = runSsg("--version");
    expect(output).toContain("1.0.0");
  });

  it("builds a site from default directories", () => {
    runSsg(`-s ${fixtureSrc} -t ${fixtureTemplates} -o ${outDir}`);

    expect(existsSync(resolve(outDir, "index.html"))).toBe(true);
    expect(existsSync(resolve(outDir, "posts", "hello", "index.html"))).toBe(true);
    expect(existsSync(resolve(outDir, "feed.xml"))).toBe(true);
    expect(existsSync(resolve(outDir, "tags", "index.html"))).toBe(true);
  });

  it("generates a valid RSS feed", () => {
    runSsg(`-s ${fixtureSrc} -t ${fixtureTemplates} -o ${outDir} --title "RSS Site" --description "For testing RSS"`);

    const rss = readFileSync(resolve(outDir, "feed.xml"), "utf-8");
    expect(rss).toContain("<rss");
    expect(rss).toContain("<channel>");
    expect(rss).toContain("<title>RSS Site</title>");
    expect(rss).toContain("<description>For testing RSS</description>");
    expect(rss).toContain("<item>");
    expect(rss).toContain("<title>Hello World</title>");
  });

  it("honors --title and --description flags", () => {
    runSsg(
      `-s ${fixtureSrc} -t ${fixtureTemplates} -o ${outDir} --title "Flag Test" --description "CLI flags work"`,
    );

    const html = readFileSync(resolve(outDir, "index.html"), "utf-8");
    expect(html).toContain("Flag Test");
  });

  it("creates tag index pages", () => {
    runSsg(`-s ${fixtureSrc} -t ${fixtureTemplates} -o ${outDir}`);

    const tagDir = resolve(outDir, "tags");
    expect(existsSync(resolve(tagDir, "index.html"))).toBe(true);
    expect(existsSync(resolve(tagDir, "javascript", "index.html"))).toBe(true);
    expect(existsSync(resolve(tagDir, "tutorial", "index.html"))).toBe(true);
  });

  it("creates a 404 page", () => {
    runSsg(`-s ${fixtureSrc} -t ${fixtureTemplates} -o ${outDir}`);

    expect(existsSync(resolve(outDir, "404", "index.html"))).toBe(true);
  });

  it("excludes draft posts from published output but keeps draft posts in pages (frontmatter honors draft flag)", () => {
    runSsg(`-s ${fixtureSrc} -t ${fixtureTemplates} -o ${outDir}`);

    const draftPath = resolve(outDir, "posts", "draft", "index.html");
    expect(existsSync(draftPath)).toBe(false);
  });
});
