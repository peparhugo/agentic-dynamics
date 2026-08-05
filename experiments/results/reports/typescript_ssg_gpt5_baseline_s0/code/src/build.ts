import path from 'path';
import fs from 'fs';
import fg from 'fast-glob';
import matter from 'gray-matter';
import { createMarkdownRenderer } from './markdown';
import { BuildOptions, BuildResult, Frontmatter, Page } from './types';
import { ensureDir, htmlInjectBeforeBodyEnd, normalizeBaseUrl, pathToUrlPath, toSlug, withHtmlExt, writeFileAtomic } from './utils';
import { loadTemplates } from './templates';
import { generateRSS } from './rss';

function normalizeTags(tags: unknown): string[] {
  if (Array.isArray(tags)) return tags.map(String);
  if (typeof tags === 'string') {
    return tags.split(',').map((s) => s.trim()).filter(Boolean);
  }
  return [];
}

export async function buildSite(opts: BuildOptions): Promise<BuildResult> {
  const srcDir = path.resolve(opts.srcDir);
  const templatesDir = path.resolve(opts.templatesDir);
  const outDir = path.resolve(opts.outDir);
  const baseUrl = normalizeBaseUrl(opts.baseUrl) || '';

  ensureDir(outDir);

  const md = createMarkdownRenderer();
  const tpls = loadTemplates(templatesDir);

  const files = fg.sync(['**/*.md'], { cwd: srcDir, onlyFiles: true });

  const pages: Page[] = [];

  for (const rel of files) {
    const full = path.join(srcDir, rel);
    const raw = fs.readFileSync(full, 'utf8');
    const parsed = matter(raw);
    const fm = parsed.data as Frontmatter;
    const draft = !!fm.draft;
    if (draft && !opts.includeDrafts) continue;

    const contentHtml = md.render(parsed.content);
    const title = fm.title || path.basename(rel, path.extname(rel));
    const slug = toSlug(title);
    const relHtml = withHtmlExt(rel);
    const urlPath = pathToUrlPath(relHtml);
    const outPath = path.join(outDir, relHtml);
    const data = {
      ...fm,
      title,
      tags: normalizeTags(fm.tags),
      draft,
      layout: (fm.layout as string) || 'main',
    } as Page['data'];

    const page: Page = { sourcePath: full, relPath: rel, outPath, urlPath, slug, contentHtml, data };
    pages.push(page);
  }

  // Build tag map
  const tags = new Map<string, Page[]>();
  for (const p of pages) {
    for (const tag of p.data.tags || []) {
      const list = tags.get(tag) || [];
      list.push(p);
      tags.set(tag, list);
    }
  }

  // Sort pages by date desc for convenience
  pages.sort((a, b) => (new Date(b.data.date || 0).getTime() - new Date(a.data.date || 0).getTime()));

  // Render pages via templates
  for (const p of pages) {
    const ctx = {
      site: { title: opts.siteTitle || '', url: opts.siteUrl || '', baseUrl },
      page: p.data,
      content: p.contentHtml,
      allPages: pages.filter((pp) => !pp.data.draft),
      tags: Array.from(tags.entries()).map(([tag, list]) => ({ tag, count: list.length })),
      urlPath: p.urlPath,
    };

    let inner = p.contentHtml;
    if (p.data.template) {
      const rendered = tpls.renderPageTemplate(p.data.template, ctx);
      if (rendered) inner = rendered;
    }
    const html = tpls.renderLayout(p.data.layout, { ...ctx, body: inner, content: inner });

    const finalHtml = opts.liveReloadClient ? htmlInjectBeforeBodyEnd(html, opts.liveReloadClient) : html;
    writeFileAtomic(p.outPath, finalHtml);
  }

  // Generate tag index pages
  if (tags.size > 0) {
    for (const [tag, list] of tags.entries()) {
      const tagRel = path.join('tags', toSlug(tag), 'index.html');
      const outPath = path.join(outDir, tagRel);
      const urlPath = pathToUrlPath(tagRel);
      const tagCtx = {
        site: { title: opts.siteTitle || '', url: opts.siteUrl || '', baseUrl },
        tag,
        pages: list.filter((pp) => !pp.data.draft),
        urlPath,
      };
      const tagContent = tpls.renderTagTemplate(tagCtx);
      const html = tpls.renderLayout('main', { ...tagCtx, body: tagContent, content: tagContent });
      const finalHtml = opts.liveReloadClient ? htmlInjectBeforeBodyEnd(html, opts.liveReloadClient) : html;
      writeFileAtomic(outPath, finalHtml);
    }
  }

  // Generate RSS if siteUrl and siteTitle are set
  if (opts.siteUrl && opts.siteTitle) {
    const xml = generateRSS({ siteTitle: opts.siteTitle, siteUrl: opts.siteUrl, baseUrl, pages });
    writeFileAtomic(path.join(outDir, 'rss.xml'), xml);
  }

  return { pages, tags };
}
