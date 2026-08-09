import path from 'node:path';
import fs from 'fs-extra';
import fg from 'fast-glob';
import matter from 'gray-matter';
import { Feed } from 'feed';
import { renderMarkdown } from './markdown.js';
import { loadTemplates } from './templates.js';
import type { BuildOptions, Frontmatter, Page } from './types.js';

function toSlug(filePath: string, sourceDir: string): string {
  const rel = path.relative(sourceDir, filePath);
  const noExt = rel.replace(/\\/g, '/').replace(/\.[^./]+$/, '');
  // put into pretty URL: <slug>/index.html
  return noExt;
}

function injectLiveReload(html: string, liveReloadUrl?: string): string {
  if (!liveReloadUrl) return html;
  const script = `\n<script>(function(){try{var ws=new WebSocket('${liveReloadUrl}');ws.onmessage=function(ev){if(ev.data==='reload'){location.reload();}};ws.onclose=function(){console.warn('Live reload disconnected');};}catch(e){console.warn('Live reload disabled',e);}})();</script>\n`;
  if (html.includes('</body>')) return html.replace('</body>', script + '</body>');
  return html + script;
}

async function loadPages(sourceDir: string, includeDrafts?: boolean): Promise<Page[]> {
  const entries = await fg(['**/*.md'], { cwd: sourceDir, absolute: true, dot: false });
  const pages: Page[] = [];
  for (const file of entries) {
    const raw = await fs.readFile(file, 'utf8');
    const parsed = matter(raw);
    const fm = parsed.data as Frontmatter;
    const draft = fm.draft === true;
    if (draft && !includeDrafts) continue;
    const html = renderMarkdown(parsed.content);
    const slug = toSlug(file, sourceDir);
    const url = '/' + slug.replace(/(^|\/)index$/, '$1') + (slug.endsWith('index') ? '' : '/');
    const date: Date | undefined = fm.date ? new Date(fm.date as any) : undefined;
    const page: Page = {
      id: slug,
      url,
      content: html,
      data: { ...fm, date },
      srcPath: file,
      outPath: '', // filled later
    };
    pages.push(page);
  }
  return pages;
}

async function copyStaticAssets(sourceDir: string, outDir: string): Promise<void> {
  const files = await fg(['**/*', '!**/*.md'], { cwd: sourceDir, absolute: true, dot: false });
  await Promise.all(
    files.map(async (abs) => {
      const rel = path.relative(sourceDir, abs);
      const dest = path.join(outDir, rel);
      await fs.ensureDir(path.dirname(dest));
      await fs.copy(abs, dest);
    })
  );
}

export async function buildSite(opts: BuildOptions): Promise<{ pages: Page[] }> {
  const { sourceDir, templatesDir, outDir, includeDrafts, clean, baseUrl, siteTitle, liveReloadUrl } = opts;
  if (clean) await fs.emptyDir(outDir); else await fs.ensureDir(outDir);

  const pages = await loadPages(sourceDir, includeDrafts);
  // sort by date desc if present
  pages.sort((a, b) => {
    const ad = a.data.date?.getTime() ?? 0;
    const bd = b.data.date?.getTime() ?? 0;
    return bd - ad;
  });

  const templates = await loadTemplates(templatesDir);

  // Render page html with templates and layouts
  for (const p of pages) {
    const templateName = p.data.template || 'post';
    const layoutName = p.data.layout || 'layout';
    const html = templates.renderWithLayout(templateName, layoutName, { ...p.data, content: p.content, url: p.url });
    const finalHtml = injectLiveReload(html, liveReloadUrl);
    const outPath = path.join(outDir, p.id, 'index.html');
    p.outPath = outPath;
    await fs.ensureDir(path.dirname(outPath));
    await fs.writeFile(outPath, finalHtml, 'utf8');
  }

  // Generate index page
  {
    const hasIndexTemplate = await fs.pathExists(path.join(templatesDir, 'index.hbs'));
    const indexHtml = hasIndexTemplate
      ? templates.renderWithLayout('index', 'layout', { pages })
      : defaultIndexHtml(pages);
    const final = injectLiveReload(indexHtml, liveReloadUrl);
    await fs.ensureDir(outDir);
    await fs.writeFile(path.join(outDir, 'index.html'), final, 'utf8');
  }

  // Tag pages
  const tagMap = new Map<string, Page[]>();
  for (const p of pages) {
    const tags = Array.isArray(p.data.tags) ? p.data.tags : [];
    for (const t of tags) {
      const key = String(t);
      if (!tagMap.has(key)) tagMap.set(key, []);
      tagMap.get(key)!.push(p);
    }
  }
  for (const [tag, list] of tagMap) {
    const data = { tag, pages: list };
    let html: string;
    const hasTagTemplate = await fs.pathExists(path.join(templatesDir, 'tag.hbs'));
    if (hasTagTemplate) html = templates.renderWithLayout('tag', 'layout', data);
    else html = defaultTagHtml(tag, list);
    const final = injectLiveReload(html, liveReloadUrl);
    const dir = path.join(outDir, 'tags', sanitizeTag(tag));
    await fs.ensureDir(dir);
    await fs.writeFile(path.join(dir, 'index.html'), final, 'utf8');
  }

  // RSS feed (RSS 2.0)
  await generateRss(pages, outDir, {
    baseUrl: baseUrl || 'http://localhost',
    siteTitle: siteTitle || 'Site',
  });

  // Copy non-md assets from source
  await copyStaticAssets(sourceDir, outDir);

  return { pages };
}

function sanitizeTag(tag: string): string {
  return tag.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
}

function defaultIndexHtml(pages: Page[]): string {
  const items = pages
    .map(
      (p) => `<li><a href="${p.url}">${escapeHtml(p.data.title || p.id)}</a>${
        p.data.date ? ` <time datetime="${p.data.date.toISOString()}">${p.data.date.toDateString()}</time>` : ''
      }</li>`
    )
    .join('\n');
  return `<!doctype html><html><head><meta charset="utf-8"><title>Index</title></head><body><h1>Posts</h1><ul>${items}</ul></body></html>`;
}

function defaultTagHtml(tag: string, pages: Page[]): string {
  const items = pages
    .map((p) => `<li><a href="${p.url}">${escapeHtml(p.data.title || p.id)}</a></li>`) 
    .join('\n');
  return `<!doctype html><html><head><meta charset="utf-8"><title>Tag: ${escapeHtml(tag)}</title></head><body><h1>Tag: ${escapeHtml(tag)}</h1><ul>${items}</ul></body></html>`;
}

function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]!));
}

async function generateRss(pages: Page[], outDir: string, info: { baseUrl: string; siteTitle: string }) {
  const feed = new Feed({
    title: info.siteTitle,
    id: info.baseUrl,
    link: info.baseUrl,
  });
  for (const p of pages) {
    feed.addItem({
      id: new URL(p.url, info.baseUrl).toString(),
      link: new URL(p.url, info.baseUrl).toString(),
      title: p.data.title || p.id,
      date: p.data.date || new Date(),
      description: '',
      content: p.content,
    });
  }
  const xml = feed.rss2();
  await fs.writeFile(path.join(outDir, 'feed.xml'), xml, 'utf8');
}
