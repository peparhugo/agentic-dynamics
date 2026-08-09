import fs from 'node:fs';
import path from 'node:path';
import { parseFrontmatter, makeExcerpt } from './frontmatter.js';
import { renderMarkdown } from './markdown.js';
import { createTemplateEngine } from './templates.js';
import { generateRss } from './rss.js';
import type { BuildResult, Page, SiteConfig } from './types.js';

function walkMarkdownFiles(dir: string, base = dir): string[] {
  if (!fs.existsSync(dir)) return [];
  const out: string[] = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...walkMarkdownFiles(full, base));
    else if (/\.(md|markdown)$/i.test(entry.name)) out.push(path.relative(base, full));
  }
  return out.sort();
}

export function slugifyTag(tag: string): string {
  return tag
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

/** Load and render one markdown source file into a Page. */
export function loadPage(sourceDir: string, relPath: string): Page {
  const raw = fs.readFileSync(path.join(sourceDir, relPath), 'utf8');
  const fallbackTitle = path.basename(relPath).replace(/\.(md|markdown)$/i, '');
  const { frontmatter, body } = parseFrontmatter(raw, fallbackTitle);
  const outputPath = relPath.replace(/\.(md|markdown)$/i, '.html');
  return {
    sourcePath: relPath,
    outputPath,
    url: '/' + outputPath.split(path.sep).join('/'),
    frontmatter,
    body,
    html: renderMarkdown(body),
    excerpt: makeExcerpt(body),
  };
}

export function collectPages(config: SiteConfig): Page[] {
  const pages = walkMarkdownFiles(config.source).map((rel) => loadPage(config.source, rel));
  return config.drafts ? pages : pages.filter((p) => !p.frontmatter.draft);
}

export function groupByTag(pages: Page[]): Map<string, Page[]> {
  const groups = new Map<string, Page[]>();
  for (const page of pages) {
    for (const tag of page.frontmatter.tags) {
      const list = groups.get(tag) ?? [];
      list.push(page);
      groups.set(tag, list);
    }
  }
  return groups;
}

function byDateDesc(a: Page, b: Page): number {
  return (b.frontmatter.date?.getTime() ?? 0) - (a.frontmatter.date?.getTime() ?? 0);
}

function writeFileEnsured(filePath: string, content: string): void {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, content);
}

export interface BuildOptions {
  /** Inject a live-reload script into every HTML page (used by dev server). */
  injectReloadScript?: string;
}

/**
 * Full site build:
 *  - each markdown file -> HTML via its template (frontmatter.layout template name, default "post")
 *  - /index.html listing all pages (template "index" if present)
 *  - /tags/<slug>.html per tag (template "tag" if present)
 *  - /feed.xml RSS feed
 */
export function buildSite(config: SiteConfig, options: BuildOptions = {}): BuildResult {
  if (!fs.existsSync(config.source)) {
    throw new Error(`Source directory not found: ${config.source}`);
  }
  const engine = createTemplateEngine(config.templates);
  const pages = collectPages(config);
  const sortedPages = [...pages].sort(byDateDesc);
  const tagGroups = groupByTag(pages);
  const allTags = [...tagGroups.keys()].sort().map((tag) => ({
    tag,
    slug: slugifyTag(tag),
    url: `/tags/${slugifyTag(tag)}.html`,
    count: tagGroups.get(tag)!.length,
  }));
  const wroteFiles: string[] = [];
  const site = { title: config.title, description: config.description, baseUrl: config.baseUrl, tags: allTags };

  const finalize = (html: string): string =>
    options.injectReloadScript ? injectBeforeBodyEnd(html, options.injectReloadScript) : html;

  // Content pages
  for (const page of pages) {
    const templateName =
      typeof page.frontmatter.template === 'string' && engine.hasTemplate(page.frontmatter.template)
        ? (page.frontmatter.template as string)
        : 'post';
    const html = engine.render(templateName, {
      ...page.frontmatter,
      content: page.html,
      url: page.url,
      excerpt: page.excerpt,
      site,
    });
    const dest = path.join(config.out, page.outputPath);
    writeFileEnsured(dest, finalize(html));
    wroteFiles.push(dest);
  }

  // Index page
  if (engine.hasTemplate('index')) {
    const html = engine.render('index', {
      title: config.title,
      pages: sortedPages.map(pageContext),
      site,
    });
    const dest = path.join(config.out, 'index.html');
    writeFileEnsured(dest, finalize(html));
    wroteFiles.push(dest);
  }

  // Tag index pages
  const tagPages: string[] = [];
  for (const { tag, slug } of allTags) {
    const tagged = [...tagGroups.get(tag)!].sort(byDateDesc);
    const html = engine.hasTemplate('tag')
      ? engine.render('tag', { title: `Tag: ${tag}`, tag, pages: tagged.map(pageContext), site })
      : fallbackTagHtml(tag, tagged);
    const dest = path.join(config.out, 'tags', `${slug}.html`);
    writeFileEnsured(dest, finalize(html));
    wroteFiles.push(dest);
    tagPages.push(dest);
  }

  // RSS feed
  const feedDest = path.join(config.out, 'feed.xml');
  writeFileEnsured(feedDest, generateRss(sortedPages, config));
  wroteFiles.push(feedDest);

  return { pages: sortedPages, tagPages, wroteFiles };
}

function pageContext(page: Page) {
  return {
    ...page.frontmatter,
    url: page.url,
    excerpt: page.excerpt,
  };
}

function fallbackTagHtml(tag: string, pages: Page[]): string {
  const items = pages
    .map((p) => `<li><a href="${p.url}">${p.frontmatter.title}</a></li>`)
    .join('\n');
  return `<!DOCTYPE html><html><head><meta charset="utf-8"><title>Tag: ${tag}</title></head><body><h1>Tag: ${tag}</h1><ul>\n${items}\n</ul></body></html>`;
}

export function injectBeforeBodyEnd(html: string, snippet: string): string {
  if (html.includes('</body>')) return html.replace('</body>', `${snippet}\n</body>`);
  return html + snippet;
}
