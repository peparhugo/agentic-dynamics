import { promises as fs } from "node:fs";
import path from "node:path";
import { parseDocument } from "./frontmatter.js";
import { renderMarkdown } from "./markdown.js";
import { createTemplateEngine, type TemplateEngine } from "./templates.js";
import { generateRss } from "./rss.js";
import type { Page, SiteConfig, SiteContext } from "./types.js";

export interface BuildResult {
  pages: Page[];
  tagPages: string[];
  wroteRss: boolean;
  skippedDrafts: number;
}

async function walkMarkdown(dir: string, base = dir): Promise<string[]> {
  const out: string[] = [];
  const entries = await fs.readdir(dir, { withFileTypes: true });
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...(await walkMarkdown(full, base)));
    else if (/\.(md|markdown)$/i.test(entry.name)) out.push(full);
  }
  return out;
}

function slugifyTag(tag: string): string {
  return tag
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export async function loadPages(config: SiteConfig): Promise<{ pages: Page[]; skippedDrafts: number }> {
  const files = await walkMarkdown(config.sourceDir);
  let skippedDrafts = 0;

  // Throughput: parse + render all files concurrently.
  const results = await Promise.all(
    files.map(async (file): Promise<Page | null> => {
      const raw = await fs.readFile(file, "utf8");
      const rel = path.relative(config.sourceDir, file).split(path.sep).join("/");
      const fallbackTitle = path.basename(rel).replace(/\.(md|markdown)$/i, "");
      const { frontmatter, body } = parseDocument(raw, fallbackTitle);
      if (frontmatter.draft && !config.includeDrafts) {
        skippedDrafts++;
        return null;
      }
      const outputPath = rel.replace(/\.(md|markdown)$/i, ".html");
      return {
        sourcePath: rel,
        outputPath,
        url: "/" + outputPath,
        frontmatter,
        body,
        html: renderMarkdown(body),
      };
    })
  );

  const pages = results.filter((p): p is Page => p !== null);
  // Deterministic order: newest first, ties broken by path.
  pages.sort((a, b) => {
    const diff = (b.frontmatter.date?.getTime() ?? 0) - (a.frontmatter.date?.getTime() ?? 0);
    return diff !== 0 ? diff : a.sourcePath.localeCompare(b.sourcePath);
  });
  return { pages, skippedDrafts };
}

export function collectTags(pages: Page[]): Record<string, Page[]> {
  const tags: Record<string, Page[]> = {};
  for (const page of pages) {
    for (const tag of page.frontmatter.tags) {
      (tags[tag] ??= []).push(page);
    }
  }
  return tags;
}

function renderPage(engine: TemplateEngine, page: Page, site: SiteContext): string {
  const layout = engine.hasLayout(page.frontmatter.layout) ? page.frontmatter.layout : "default";
  return engine.render(layout, {
    ...page.frontmatter,
    content: page.html,
    page,
    site,
  });
}

async function writeFile(outputDir: string, relPath: string, content: string): Promise<void> {
  const full = path.join(outputDir, relPath);
  await fs.mkdir(path.dirname(full), { recursive: true });
  await fs.writeFile(full, content, "utf8");
}

/** Full site build: pages, tag index pages, RSS feed. */
export async function buildSite(config: SiteConfig): Promise<BuildResult> {
  const [engine, loaded] = await Promise.all([
    createTemplateEngine(config.templateDir),
    loadPages(config),
  ]);
  const { pages, skippedDrafts } = loaded;
  const tags = collectTags(pages);
  const site: SiteContext = {
    title: config.siteTitle,
    url: config.siteUrl,
    description: config.siteDescription,
    pages,
    tags,
  };

  await fs.mkdir(config.outputDir, { recursive: true });

  // Throughput: all writes issued concurrently.
  const writes: Promise<void>[] = pages.map((page) =>
    writeFile(config.outputDir, page.outputPath, renderPage(engine, page, site))
  );

  // Tag index pages: /tags/<slug>.html using the "tag" layout if present.
  const tagPages: string[] = [];
  for (const [tag, tagged] of Object.entries(tags)) {
    const rel = path.posix.join("tags", `${slugifyTag(tag)}.html`);
    tagPages.push(rel);
    const html = engine.hasLayout("tag")
      ? engine.render("tag", { tag, pages: tagged, site })
      : defaultTagIndex(tag, tagged);
    writes.push(writeFile(config.outputDir, rel, html));
  }

  // RSS feed at /feed.xml
  writes.push(writeFile(config.outputDir, "feed.xml", generateRss(config, pages)));

  await Promise.all(writes);
  return { pages, tagPages, wroteRss: true, skippedDrafts };
}

function defaultTagIndex(tag: string, pages: Page[]): string {
  const items = pages
    .map((p) => `<li><a href="${p.url}">${p.frontmatter.title}</a></li>`)
    .join("\n      ");
  return `<!doctype html>
<html>
<head><meta charset="utf-8"><title>Tag: ${tag}</title></head>
<body>
  <h1>Tag: ${tag}</h1>
  <ul>
      ${items}
  </ul>
</body>
</html>
`;
}
