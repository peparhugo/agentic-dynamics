import { readFileSync, readdirSync, mkdirSync, writeFileSync, existsSync } from "node:fs";
import { join, relative, dirname, extname } from "node:path";
import { marked } from "marked";
import { SiteConfig, Page } from "./types.js";
import { parseFrontmatter } from "./frontmatter.js";
import { loadTemplates } from "./templates.js";
import { highlightCode } from "./highlighting.js";
import { generateRss } from "./rss.js";
import { buildTagMap, generateTagPages } from "./tags.js";

export function build(config: SiteConfig): void {
  const { renderPage } = loadTemplates(config);

  const pages = collectPages(config);
  const published = pages.filter((p) => !p.frontmatter.draft);

  const tagMap = buildTagMap(published);
  const tagPages = generateTagPages(tagMap, renderPage, config);

  for (const page of [...published, ...tagPages]) {
    page.html = renderPage(page, published);
    writeOutput(page, config);
  }

  const rss = generateRss(published, config);
  mkdirSync(config.outputDir, { recursive: true });
  writeFileSync(join(config.outputDir, "rss.xml"), rss);
}

function collectPages(config: SiteConfig): Page[] {
  const pages: Page[] = [];

  function walk(dir: string): void {
    if (!existsSync(dir)) return;
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const full = join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(full);
      } else if (entry.name.endsWith(".md")) {
        const page = processMarkdownFile(full, config);
        if (page) pages.push(page);
      }
    }
  }

  walk(config.sourceDir);
  return pages;
}

function processMarkdownFile(filePath: string, config: SiteConfig): Page | null {
  const raw = readFileSync(filePath, "utf-8");
  const { frontmatter, content } = parseFrontmatter(raw);

  const relPath = relative(config.sourceDir, filePath);
  const url = relPath.replace(/\.md$/, ".html");
  const outPath = relPath.replace(/\.md$/, ".html");

  let html = marked.parse(content) as string;
  html = highlightCode(html);

  return {
    path: outPath,
    frontmatter,
    content,
    html,
    url,
  };
}

function writeOutput(page: Page, config: SiteConfig): void {
  const outPath = join(config.outputDir, page.path);
  mkdirSync(dirname(outPath), { recursive: true });
  writeFileSync(outPath, page.html);
}
