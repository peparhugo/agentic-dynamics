import fs from "node:fs";
import path from "node:path";
import { parseFrontmatter } from "./frontmatter.js";
import { renderMarkdown } from "./markdown.js";
import { loadTemplates, type TemplateSet } from "./templates.js";
import { generateRss } from "./rss.js";
import type { Page, SiteConfig } from "./types.js";

export interface BuildResult {
  pages: Page[];
  tags: Map<string, Page[]>;
  written: string[];
}

/** Recursively list files under dir matching a predicate. */
export function listFiles(dir: string, filter: (f: string) => boolean): string[] {
  const out: string[] = [];
  const walk = (d: string) => {
    for (const entry of fs.readdirSync(d, { withFileTypes: true })) {
      const full = path.join(d, entry.name);
      if (entry.isDirectory()) walk(full);
      else if (filter(entry.name)) out.push(full);
    }
  };
  if (fs.existsSync(dir)) walk(dir);
  return out;
}

/** Load and render one markdown source file into a Page (no layout applied yet). */
export function loadPage(sourceDir: string, absFile: string): Page {
  const rel = path.relative(sourceDir, absFile);
  const src = fs.readFileSync(absFile, "utf8");
  const { frontmatter, body } = parseFrontmatter(src);
  const outPath = rel.replace(/\.md$/i, ".html").split(path.sep).join("/");
  return {
    sourcePath: rel.split(path.sep).join("/"),
    outPath,
    urlPath: "/" + outPath,
    frontmatter,
    html: renderMarkdown(body),
    raw: body,
  };
}

function pageContext(p: Page, config: SiteConfig) {
  return {
    ...p.frontmatter.extra,
    title: p.frontmatter.title,
    date: p.frontmatter.date,
    tags: p.frontmatter.tags,
    draft: p.frontmatter.draft,
    content: p.html, // use {{{content}}} in layouts
    url: p.urlPath,
    site: { title: config.siteTitle, description: config.siteDescription, baseUrl: config.baseUrl },
  };
}

function writeOut(outDir: string, relPath: string, content: string, written: string[]): void {
  const abs = path.join(outDir, relPath);
  fs.mkdirSync(path.dirname(abs), { recursive: true });
  fs.writeFileSync(abs, content);
  written.push(relPath);
}

/** Collect pages, honoring the draft flag. */
export function collectPages(config: SiteConfig): Page[] {
  const files = listFiles(config.sourceDir, (f) => f.toLowerCase().endsWith(".md"));
  const pages = files.map((f) => loadPage(config.sourceDir, f));
  return config.includeDrafts ? pages : pages.filter((p) => !p.frontmatter.draft);
}

export function groupByTag(pages: Page[]): Map<string, Page[]> {
  const tags = new Map<string, Page[]>();
  for (const p of pages) {
    for (const t of p.frontmatter.tags) {
      const list = tags.get(t) ?? [];
      list.push(p);
      tags.set(t, list);
    }
  }
  return tags;
}

/** Full site build: pages, tag index pages, index, rss.xml. */
export function buildSite(config: SiteConfig): BuildResult {
  const templates = loadTemplates(config.templateDir);
  const pages = collectPages(config);
  const written: string[] = [];

  const sorted = [...pages].sort(
    (a, b) => (b.frontmatter.date?.getTime() ?? 0) - (a.frontmatter.date?.getTime() ?? 0)
  );

  for (const p of pages) {
    written.push(...renderPageToDisk(p, templates, config, sorted));
  }

  // Tag index pages: /tags/<tag>.html
  const tags = groupByTag(pages);
  for (const [tag, tagPages] of tags) {
    const ctx = {
      title: `Tag: ${tag}`,
      tag,
      pages: tagPages.map((p) => pageContext(p, config)),
      site: { title: config.siteTitle, description: config.siteDescription, baseUrl: config.baseUrl },
    };
    const layout = templates.has("tag") ? "tag" : "default";
    writeOut(config.outDir, `tags/${slugify(tag)}.html`, templates.renderLayout(layout, ctx), written);
  }

  // Site index (if an index.hbs layout exists and no content index.md produced one)
  if (templates.has("index") && !pages.some((p) => p.outPath === "index.html")) {
    const ctx = {
      title: config.siteTitle,
      pages: sorted.map((p) => pageContext(p, config)),
      tags: [...tags.keys()].sort(),
      site: { title: config.siteTitle, description: config.siteDescription, baseUrl: config.baseUrl },
    };
    writeOut(config.outDir, "index.html", templates.renderLayout("index", ctx), written);
  }

  // RSS
  writeOut(config.outDir, "rss.xml", generateRss(pages, config), written);

  return { pages, tags, written };
}

/** Render a single page through its layout and write it. Used by full build and incremental rebuilds. */
export function renderPageToDisk(
  page: Page,
  templates: TemplateSet,
  config: SiteConfig,
  allSorted: Page[]
): string[] {
  const written: string[] = [];
  const ctx = { ...pageContext(page, config), pages: allSorted.map((p) => pageContext(p, config)) };
  writeOut(config.outDir, page.outPath, templates.renderLayout(page.frontmatter.layout, ctx), written);
  return written;
}

export function slugify(s: string): string {
  return s
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}
