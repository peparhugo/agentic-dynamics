import { mkdirSync, writeFileSync, existsSync, readdirSync, statSync, copyFileSync } from "node:fs";
import { join, relative, dirname } from "node:path";
import { globSync } from "node:fs";
import type { Page, SiteConfig, BuildContext } from "./types.js";
import { parseFrontmatter } from "./frontmatter.js";
import { renderMarkdown } from "./markdown.js";
import { initTemplates, renderWithLayout, renderTemplate, templateExists } from "./templates.js";
import { generateRSS } from "./rss.js";

function walkDir(dir: string): string[] {
  const results: string[] = [];
  const entries = readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      results.push(...walkDir(full));
    } else if (entry.name.endsWith(".md")) {
      results.push(full);
    }
  }
  return results;
}

export function build(config: SiteConfig): void {
  initTemplates(config.templates);

  const sourceFiles = walkDir(config.source);
  let pages: Page[] = [];

  for (const file of sourceFiles) {
    const page = parseFrontmatter(file, config.source);
    if (!page) continue;
    if (page.frontmatter.draft && !config.includeDrafts) continue;
    page.html = renderMarkdown(page.markdown);
    pages.push(page);
  }

  pages.sort((a, b) => {
    const da = a.frontmatter.date ? new Date(a.frontmatter.date).getTime() : 0;
    const db = b.frontmatter.date ? new Date(b.frontmatter.date).getTime() : 0;
    return db - da;
  });

  const tagMap = new Map<string, Page[]>();
  for (const page of pages) {
    for (const tag of page.frontmatter.tags || []) {
      const key = tag.toLowerCase().replace(/\s+/g, "-");
      if (!tagMap.has(key)) tagMap.set(key, []);
      tagMap.get(key)!.push(page);
    }
  }

  // Sort each tag's pages by date
  for (const [, tagPages] of tagMap) {
    tagPages.sort((a, b) => {
      const da = a.frontmatter.date ? new Date(a.frontmatter.date).getTime() : 0;
      const db = b.frontmatter.date ? new Date(b.frontmatter.date).getTime() : 0;
      return db - da;
    });
  }

  const ctx: BuildContext = { config, pages, tagMap };

  // Generate post pages
  const layout = "default";
  const postTemplate = templateExists("post") ? "post" : null;

  for (const page of pages) {
    const outputFile = join(config.output, page.outputPath);
    mkdirSync(dirname(outputFile), { recursive: true });
    const data = {
      ...page.frontmatter,
      content: page.html,
      url: page.url,
      page,
      pages,
      site: { title: config.siteTitle, description: config.siteDescription, baseUrl: config.baseUrl },
    };
    const rendered = postTemplate
      ? renderWithLayout(postTemplate, layout, data)
      : renderTemplate("layout:" + layout, { ...data, body: page.html });
    writeFileSync(outputFile, rendered);
  }

  // Generate index page
  if (templateExists("index")) {
    const indexFile = join(config.output, "index.html");
    mkdirSync(dirname(indexFile), { recursive: true });
    const data = {
      pages,
      site: { title: config.siteTitle, description: config.siteDescription, baseUrl: config.baseUrl },
    };
    writeFileSync(indexFile, renderWithLayout("index", layout, data));
  }

  // Generate tag pages
  if (templateExists("tag")) {
    for (const [tag, tagPages] of tagMap) {
      const tagFile = join(config.output, "tags", tag, "index.html");
      mkdirSync(dirname(tagFile), { recursive: true });
      const data = {
        tag,
        pages: tagPages,
        allTags: Array.from(tagMap.keys()).sort(),
        site: { title: config.siteTitle, description: config.siteDescription, baseUrl: config.baseUrl },
      };
      writeFileSync(tagFile, renderWithLayout("tag", layout, data));
    }
  }

  // Generate RSS
  const rssXml = generateRSS(pages, config);
  writeFileSync(join(config.output, "rss.xml"), rssXml);

  // Copy static assets from templates/assets if they exist
  const assetsDir = join(config.templates, "assets");
  if (existsSync(assetsDir)) {
    copyAssets(assetsDir, config.output);
  }
}

function copyAssets(src: string, dest: string): void {
  const entries = readdirSync(src, { withFileTypes: true });
  for (const entry of entries) {
    const srcPath = join(src, entry.name);
    const destPath = join(dest, entry.name);
    if (entry.isDirectory()) {
      mkdirSync(destPath, { recursive: true });
      copyAssets(srcPath, destPath);
    } else {
      mkdirSync(dirname(destPath), { recursive: true });
      copyFileSync(srcPath, destPath);
    }
  }
}
