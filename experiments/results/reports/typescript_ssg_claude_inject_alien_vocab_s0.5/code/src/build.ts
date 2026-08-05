import { promises as fs } from 'node:fs';
import path from 'node:path';
import { parseFrontmatter } from './frontmatter.js';
import { renderMarkdown, extractExcerpt } from './markdown.js';
import { TemplateEngine } from './templates.js';
import { generateRss } from './rss.js';
import type { BuildResult, Page, SiteConfig } from './types.js';

/** Recursively list files under `dir`, returning paths relative to it. */
async function walk(dir: string, prefix = ''): Promise<string[]> {
  const out: string[] = [];
  const entries = await fs.readdir(dir, { withFileTypes: true });
  for (const entry of entries) {
    const rel = prefix ? `${prefix}/${entry.name}` : entry.name;
    if (entry.isDirectory()) out.push(...(await walk(path.join(dir, entry.name), rel)));
    else out.push(rel);
  }
  return out;
}

/** "posts/hello.md" -> { outputPath: "posts/hello/index.html", url: "/posts/hello/" } */
export function toOutputPath(sourcePath: string): { outputPath: string; url: string } {
  const noExt = sourcePath.replace(/\.(md|markdown)$/i, '');
  if (path.basename(noExt) === 'index') {
    const dir = path.dirname(noExt);
    const base = dir === '.' ? '' : `${dir}/`;
    return { outputPath: `${base}index.html`, url: `/${base}` };
  }
  return { outputPath: `${noExt}/index.html`, url: `/${noExt}/` };
}

export function slugifyTag(tag: string): string {
  return tag
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

/** Load and parse all markdown pages from the source directory. */
export async function loadPages(config: SiteConfig): Promise<Page[]> {
  const files = (await walk(config.sourceDir)).filter((f) => /\.(md|markdown)$/i.test(f));
  const pages: Page[] = [];
  for (const rel of files) {
    const raw = await fs.readFile(path.join(config.sourceDir, rel), 'utf8');
    const fallbackTitle = path.basename(rel).replace(/\.(md|markdown)$/i, '');
    const { frontmatter, body } = parseFrontmatter(raw, fallbackTitle);
    if (frontmatter.draft && !config.includeDrafts) continue;
    const { outputPath, url } = toOutputPath(rel);
    pages.push({
      sourcePath: rel,
      outputPath,
      url,
      frontmatter,
      body,
      html: renderMarkdown(body),
      excerpt:
        typeof frontmatter.description === 'string'
          ? frontmatter.description
          : extractExcerpt(body),
    });
  }
  // Newest first; undated pages sink to the bottom, then alphabetical.
  pages.sort((a, b) => {
    const at = a.frontmatter.date?.getTime() ?? -Infinity;
    const bt = b.frontmatter.date?.getTime() ?? -Infinity;
    return bt - at || a.frontmatter.title.localeCompare(b.frontmatter.title);
  });
  return pages;
}

/** Group pages by tag. Map key is the original tag name. */
export function collectTags(pages: Page[]): Map<string, Page[]> {
  const tags = new Map<string, Page[]>();
  for (const page of pages) {
    for (const tag of page.frontmatter.tags) {
      const list = tags.get(tag) ?? [];
      list.push(page);
      tags.set(tag, list);
    }
  }
  return tags;
}

async function writeFileDeep(filePath: string, content: string): Promise<void> {
  await fs.mkdir(path.dirname(filePath), { recursive: true });
  await fs.writeFile(filePath, content, 'utf8');
}

/** Copy non-markdown files from source dir into the output dir verbatim. */
async function copyStatic(config: SiteConfig, files: string[]): Promise<string[]> {
  const copied: string[] = [];
  for (const rel of files) {
    if (/\.(md|markdown)$/i.test(rel)) continue;
    const dest = path.join(config.outDir, rel);
    await fs.mkdir(path.dirname(dest), { recursive: true });
    await fs.copyFile(path.join(config.sourceDir, rel), dest);
    copied.push(rel);
  }
  return copied;
}

/**
 * Full site build: pages, tag index pages, RSS feed, static assets.
 * Template resolution per page: layout = frontmatter.layout ?? "default";
 * body template = "page" if present, otherwise the raw HTML flows straight
 * into the layout as {{{content}}}.
 */
export async function buildSite(config: SiteConfig): Promise<BuildResult> {
  const engine = new TemplateEngine();
  await engine.loadDirectory(config.templateDir);

  const pages = await loadPages(config);
  const tags = collectTags(pages);
  const filesWritten: string[] = [];

  const site = {
    title: config.title,
    description: config.description,
    baseUrl: config.baseUrl,
    pages,
    tags: [...tags.keys()].sort(),
  };

  for (const page of pages) {
    const context = { site, page, ...page.frontmatter, content: page.html };
    const layout = page.frontmatter.layout ?? 'default';
    const html = engine.hasTemplate('page')
      ? engine.renderPage({ layout, template: 'page', context })
      : engine.renderPage({ layout, content: page.html, context });
    await writeFileDeep(path.join(config.outDir, page.outputPath), html);
    filesWritten.push(page.outputPath);
  }

  // Tag index pages: /tags/<slug>/index.html
  const tagPages: string[] = [];
  for (const [tag, tagged] of tags) {
    const slug = slugifyTag(tag);
    const outputPath = `tags/${slug}/index.html`;
    const context = { site, tag, slug, pages: tagged, title: `Tagged: ${tag}` };
    const html = engine.hasTemplate('tag')
      ? engine.renderPage({ layout: 'default', template: 'tag', context })
      : engine.renderPage({
          layout: 'default',
          content: renderTagFallback(tag, tagged),
          context,
        });
    await writeFileDeep(path.join(config.outDir, outputPath), html);
    filesWritten.push(outputPath);
    tagPages.push(outputPath);
  }

  // RSS feed
  const rss = generateRss(pages, config);
  await writeFileDeep(path.join(config.outDir, 'feed.xml'), rss);
  filesWritten.push('feed.xml');

  // Static passthrough (images, css living beside content)
  const allFiles = await walk(config.sourceDir);
  filesWritten.push(...(await copyStatic(config, allFiles)));

  return { pages, tagPages, filesWritten };
}

function renderTagFallback(tag: string, pages: Page[]): string {
  const items = pages
    .map((p) => `<li><a href="${p.url}">${p.frontmatter.title}</a></li>`)
    .join('\n');
  return `<h1>Tagged: ${tag}</h1>\n<ul>\n${items}\n</ul>`;
}
