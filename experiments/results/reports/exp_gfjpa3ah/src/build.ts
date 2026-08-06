import { promises as fs } from 'node:fs';
import path from 'node:path';
import { parseDocument, slugify } from './frontmatter.js';
import { renderMarkdown, extractExcerpt } from './markdown.js';
import { createTemplateEngine } from './templates.js';
import { generateRss } from './rss.js';
import type { BuildResult, Page, SiteConfig } from './types.js';

/** Recursively list files under `dir`, returning paths relative to `dir`. */
async function listFiles(dir: string, prefix = ''): Promise<string[]> {
  const out: string[] = [];
  const entries = await fs.readdir(dir, { withFileTypes: true });
  for (const entry of entries) {
    if (entry.name.startsWith('.')) continue;
    const rel = path.join(prefix, entry.name);
    if (entry.isDirectory()) {
      out.push(...(await listFiles(path.join(dir, entry.name), rel)));
    } else {
      out.push(rel);
    }
  }
  return out;
}

/** Map a source markdown path to a pretty output path and URL. */
export function outputPathFor(sourcePath: string, slugOverride?: string): { outputPath: string; url: string } {
  const parsed = path.parse(sourcePath);
  const name = slugOverride ?? slugify(parsed.name);
  const dir = parsed.dir.split(path.sep).filter(Boolean).map(slugify).join('/');
  if (name === 'index') {
    const outputPath = dir ? `${dir}/index.html` : 'index.html';
    return { outputPath, url: `/${dir ? `${dir}/` : ''}` };
  }
  const base = dir ? `${dir}/${name}` : name;
  return { outputPath: `${base}/index.html`, url: `/${base}/` };
}

async function loadPage(sourceDir: string, sourcePath: string): Promise<Page> {
  const raw = await fs.readFile(path.join(sourceDir, sourcePath), 'utf8');
  const fallbackTitle = path.parse(sourcePath).name;
  const { frontmatter, body } = parseDocument(raw, fallbackTitle);
  const { outputPath, url } = outputPathFor(sourcePath, frontmatter.slug);
  const html = renderMarkdown(body);
  const excerpt = frontmatter.description || extractExcerpt(body);
  return { sourcePath, outputPath, url, frontmatter, body, html, excerpt };
}

/** Collect pages grouped by tag (tag display name preserved from first occurrence). */
export function collectTags(pages: Page[]): Record<string, Page[]> {
  const tags: Record<string, Page[]> = {};
  for (const page of pages) {
    for (const tag of page.frontmatter.tags) {
      const key = tag.toLowerCase();
      (tags[key] ??= []).push(page);
    }
  }
  return tags;
}

async function writeFile(outDir: string, relPath: string, content: string): Promise<void> {
  const abs = path.join(outDir, relPath);
  await fs.mkdir(path.dirname(abs), { recursive: true });
  await fs.writeFile(abs, content, 'utf8');
}

export interface BuildOptions {
  /** Extra HTML injected before </body> of every page (used for live reload). */
  injectHtml?: string;
}

export async function build(config: SiteConfig, options: BuildOptions = {}): Promise<BuildResult> {
  const engine = await createTemplateEngine(config.templateDir);
  const written: string[] = [];

  if (config.clean) {
    await fs.rm(config.outDir, { recursive: true, force: true });
  }
  await fs.mkdir(config.outDir, { recursive: true });

  const files = await listFiles(config.sourceDir);
  const markdownFiles = files.filter((f) => f.endsWith('.md'));
  const assetFiles = files.filter((f) => !f.endsWith('.md'));

  let pages = await Promise.all(markdownFiles.map((f) => loadPage(config.sourceDir, f)));
  if (!config.includeDrafts) {
    pages = pages.filter((p) => !p.frontmatter.draft);
  }

  // Newest first; undated pages sort last.
  const posts = pages
    .filter((p) => p.frontmatter.date !== null)
    .sort((a, b) => b.frontmatter.date!.getTime() - a.frontmatter.date!.getTime());
  const tags = collectTags(pages);
  const tagList = Object.keys(tags)
    .sort()
    .map((t) => ({ name: t, url: `/tags/${slugify(t)}/`, count: tags[t].length }));

  const site = {
    title: config.title,
    description: config.description,
    baseUrl: config.baseUrl,
    tags: tagList,
  };
  const finalize = (html: string) =>
    options.injectHtml ? injectBeforeBodyEnd(html, options.injectHtml) : html;

  // Content pages.
  for (const page of pages) {
    const html = engine.render(page.frontmatter.layout, {
      ...page.frontmatter,
      content: page.html,
      excerpt: page.excerpt,
      url: page.url,
      page,
      site,
      posts,
      pages,
    });
    await writeFile(config.outDir, page.outputPath, finalize(html));
    written.push(page.outputPath);
  }

  // Tag index pages.
  const tagLayout = engine.hasLayout('tag') ? 'tag' : 'default';
  for (const [tag, tagged] of Object.entries(tags)) {
    const outputPath = `tags/${slugify(tag)}/index.html`;
    const html = engine.render(tagLayout, {
      title: `Tag: ${tag}`,
      tag,
      posts: tagged
        .slice()
        .sort((a, b) => (b.frontmatter.date?.getTime() ?? 0) - (a.frontmatter.date?.getTime() ?? 0)),
      site,
      url: `/tags/${slugify(tag)}/`,
    });
    await writeFile(config.outDir, outputPath, finalize(html));
    written.push(outputPath);
  }

  // All-tags index.
  if (tagList.length > 0) {
    const layout = engine.hasLayout('tags') ? 'tags' : 'default';
    const html = engine.render(layout, { title: 'Tags', tags: tagList, site, url: '/tags/' });
    await writeFile(config.outDir, 'tags/index.html', finalize(html));
    written.push('tags/index.html');
  }

  // RSS feed.
  await writeFile(config.outDir, 'feed.xml', generateRss(pages, config));
  written.push('feed.xml');

  // Pass through non-markdown assets (images, css, ...).
  for (const asset of assetFiles) {
    const dest = path.join(config.outDir, asset);
    await fs.mkdir(path.dirname(dest), { recursive: true });
    await fs.copyFile(path.join(config.sourceDir, asset), dest);
    written.push(asset);
  }

  return { pages, tags, written };
}

export function injectBeforeBodyEnd(html: string, snippet: string): string {
  const idx = html.lastIndexOf('</body>');
  if (idx === -1) return html + snippet;
  return html.slice(0, idx) + snippet + html.slice(idx);
}
