import fs from 'node:fs';
import path from 'node:path';
import { loadContent } from './content.js';
import { slugify } from './frontmatter.js';
import { generateRss } from './rss.js';
import { createTemplateEngine } from './templates.js';
import type { BuildResult, Page, SiteConfig } from './types.js';

interface TagGroup {
  tag: string;
  slug: string;
  pages: Page[];
}

function groupByTag(pages: Page[]): TagGroup[] {
  const groups = new Map<string, TagGroup>();
  for (const page of pages) {
    for (const tag of page.frontmatter.tags) {
      const slug = slugify(tag);
      const group = groups.get(slug) ?? { tag, slug, pages: [] };
      group.pages.push(page);
      groups.set(slug, group);
    }
  }
  return [...groups.values()].sort((a, b) => a.tag.localeCompare(b.tag));
}

function writeFile(outputDir: string, relPath: string, contents: string | Buffer): string {
  const full = path.join(outputDir, relPath);
  fs.mkdirSync(path.dirname(full), { recursive: true });
  fs.writeFileSync(full, contents);
  return relPath;
}

function pageContext(page: Page, site: Record<string, unknown>, pages: Page[]) {
  return {
    site,
    pages,
    page,
    title: page.frontmatter.title,
    date: page.frontmatter.date,
    tags: page.frontmatter.tags,
    description: page.frontmatter.description ?? page.excerpt,
    content: page.html, // use {{{content}}} in layouts
    url: page.url,
  };
}

/** Build the whole site: pages, tag indexes, RSS feed, static assets. */
export function buildSite(config: SiteConfig): BuildResult {
  const engine = createTemplateEngine(config.templateDir);
  const { pages, assets } = loadContent(config.sourceDir, config.includeDrafts);
  const outputFiles: string[] = [];

  if (config.clean && fs.existsSync(config.outputDir)) {
    fs.rmSync(config.outputDir, { recursive: true });
  }
  fs.mkdirSync(config.outputDir, { recursive: true });

  const tagGroups = groupByTag(pages);
  const site = {
    title: config.title,
    description: config.description,
    baseUrl: config.baseUrl,
    tags: tagGroups.map((g) => ({ tag: g.tag, slug: g.slug, count: g.pages.length, url: `/tags/${g.slug}/` })),
  };

  // Content pages.
  for (const page of pages) {
    const html = engine.render(page.frontmatter.layout, pageContext(page, site, pages));
    outputFiles.push(writeFile(config.outputDir, page.outputPath, html));
  }

  // Per-tag index pages (layout "tag", falling back to "default").
  const tagPages: string[] = [];
  for (const group of tagGroups) {
    const rel = path.posix.join('tags', group.slug, 'index.html');
    const html = engine.render('tag', {
      site,
      pages: group.pages,
      tag: group.tag,
      title: `Posts tagged “${group.tag}”`,
      url: `/tags/${group.slug}/`,
    });
    tagPages.push(rel);
    outputFiles.push(writeFile(config.outputDir, rel, html));
  }

  // All-tags index (layout "tags", falling back to "default").
  if (tagGroups.length > 0) {
    const rel = path.posix.join('tags', 'index.html');
    const html = engine.render('tags', { site, title: 'Tags', tags: site.tags, url: '/tags/' });
    tagPages.push(rel);
    outputFiles.push(writeFile(config.outputDir, rel, html));
  }

  // RSS feed.
  outputFiles.push(writeFile(config.outputDir, 'feed.xml', generateRss(pages, config)));

  // Static assets copied through verbatim.
  for (const asset of assets) {
    const src = path.join(config.sourceDir, asset);
    const dest = path.join(config.outputDir, asset);
    fs.mkdirSync(path.dirname(dest), { recursive: true });
    fs.copyFileSync(src, dest);
    outputFiles.push(asset);
  }

  return { pages, tagPages, assets, outputFiles };
}
