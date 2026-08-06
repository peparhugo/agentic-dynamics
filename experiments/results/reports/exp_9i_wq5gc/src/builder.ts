import fs from 'node:fs';
import path from 'node:path';
import fg from 'fast-glob';
import matter from 'gray-matter';
import { BuildOptions, FrontMatter, Page, PageMeta, SiteData } from './types';
import { renderMarkdown } from './markdown';
import { loadTemplates, renderWithLayout } from './templates';

function ensureDir(p: string) {
  fs.mkdirSync(p, { recursive: true });
}

function isMarkdown(file: string) {
  return /\.(md|markdown)$/i.test(file);
}

export function parseFrontMatter(src: string): { content: string; data: FrontMatter } {
  const fm = matter(src);
  return { content: fm.content, data: (fm.data || {}) as FrontMatter };
}

function toUrl(relPath: string): string {
  const ext = path.extname(relPath);
  const noExt = relPath.slice(0, relPath.length - ext.length);
  const base = path.basename(noExt);
  const dir = path.dirname(noExt);
  if (base.toLowerCase() === 'index') {
    return '/' + (dir === '.' ? '' : dir + '/');
  }
  return '/' + (dir === '.' ? '' : dir + '/') + base + '/';
}

function outputPathFor(outDir: string, url: string): string {
  // url like "/foo/bar/" => out/foo/bar/index.html
  const rel = path.join(url.replace(/^\//, ''), 'index.html');
  return path.join(outDir, rel);
}

function collectPages(srcDir: string, includeDrafts: boolean): Page[] {
  const entries = fg.sync(['**/*'], { cwd: srcDir, dot: false, onlyFiles: true });
  const pages: Page[] = [];
  for (const rel of entries) {
    if (!isMarkdown(rel)) continue;
    const full = path.join(srcDir, rel);
    const raw = fs.readFileSync(full, 'utf8');
    const { content, data } = parseFrontMatter(raw);
    const tags = Array.isArray(data.tags)
      ? data.tags.map(String)
      : data.tags
      ? String(data.tags)
          .split(',')
          .map((t) => t.trim())
          .filter(Boolean)
      : [];
    const draft = !!data.draft;
    if (draft && !includeDrafts) continue;
    const url = toUrl(rel);
    const date = data.date ? new Date(String(data.date)) : null;
    const page: Page = {
      title: data.title,
      date: date && !isNaN(date.getTime()) ? date : null,
      tags,
      draft,
      slug: data.slug || path.basename(url.replace(/\/$/, '')) || 'index',
      layout: data.layout || 'default',
      sourcePath: full,
      url,
      bodyHtml: renderMarkdown(content),
    };
    pages.push(page);
  }
  return pages;
}

function writeFileAtomic(dest: string, content: string) {
  ensureDir(path.dirname(dest));
  fs.writeFileSync(dest, content, 'utf8');
}

function copyStaticAssets(srcDir: string, outDir: string) {
  const assets = fg.sync(['**/*', '!**/*.md', '!**/*.markdown'], { cwd: srcDir, dot: false, onlyFiles: true });
  for (const rel of assets) {
    const src = path.join(srcDir, rel);
    const dest = path.join(outDir, rel);
    ensureDir(path.dirname(dest));
    fs.copyFileSync(src, dest);
  }
}

function buildSiteData(pages: Page[], baseUrl?: string): SiteData {
  const metas: PageMeta[] = pages.map(({ bodyHtml, ...meta }) => meta);
  const tags: Record<string, PageMeta[]> = {};
  for (const p of metas) {
    for (const t of p.tags) {
      if (!tags[t]) tags[t] = [];
      tags[t].push(p);
    }
  }
  // Sort pages in each tag by date desc
  for (const t of Object.keys(tags)) {
    tags[t].sort((a, b) => (b.date?.getTime() || 0) - (a.date?.getTime() || 0));
  }
  // Sort pages globally
  metas.sort((a, b) => (b.date?.getTime() || 0) - (a.date?.getTime() || 0));
  return { baseUrl, buildTime: new Date().toISOString(), pages: metas, tags };
}

function injectLiveReload(html: string, port: number): string {
  const script = `\n<script>(()=>{try{var ws=new WebSocket('ws://'+location.hostname+':${port}/livereload');ws.onmessage=function(m){if(m.data==='reload') location.reload();};}catch(e){console.warn('livereload failed',e);}})();</script>`;
  if (html.includes('</body>')) return html.replace('</body>', script + '\n</body>');
  return html + script;
}

function renderTagPage(layouts: ReturnType<typeof loadTemplates>['layouts'], tag: string, pages: PageMeta[], site: SiteData): string {
  // Try a dedicated layout named "tag" if present, else fallback
  const ctx = { tag, pages, site, page: { title: `Tag: ${tag}` }, body: '' };
  const html = renderWithLayout(layouts, 'tag', ctx);
  // If default layout got used, there will be no listing. Provide a minimal fallback listing if 'tag' layout is missing.
  if (!layouts.get('tag') && layouts.get('default')) {
    const list = '<ul>' + pages.map((p) => `<li><a href="${p.url}">${escapeHtml(p.title || p.url)}</a></li>`).join('') + '</ul>';
    const alt = renderWithLayout(layouts, 'default', { ...ctx, body: list });
    return alt;
  }
  return html;
}

function escapeHtml(str: string): string {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function generateRss(site: SiteData): string {
  const title = 'Site Feed';
  const link = site.baseUrl || '';
  const description = 'RSS Feed';
  const items = site.pages
    .filter((p) => !!p.date)
    .slice(0, 50)
    .map((p) => {
      const itemLink = site.baseUrl ? new URL(p.url.replace(/^\//, ''), site.baseUrl).toString() : p.url;
      return `\n    <item>\n      <title>${escapeHtml(p.title || p.url)}</title>\n      <link>${escapeHtml(itemLink)}</link>\n      <guid>${escapeHtml(itemLink)}</guid>\n      <pubDate>${p.date?.toUTCString() || ''}</pubDate>\n    </item>`;
    })
    .join('');
  const xml = `<?xml version="1.0" encoding="UTF-8" ?>\n<rss version="2.0">\n  <channel>\n    <title>${escapeHtml(title)}</title>\n    <link>${escapeHtml(link)}</link>\n    <description>${escapeHtml(description)}</description>\n    <lastBuildDate>${escapeHtml(new Date(site.buildTime).toUTCString())}</lastBuildDate>${items}\n  </channel>\n</rss>\n`;
  return xml;
}

export async function buildSite(options: BuildOptions): Promise<{ site: SiteData; pages: Page[] } > {
  const { srcDir, templatesDir, outDir, includeDrafts = false, baseUrl, cleanOutDir = false, devServerPort } = options;
  if (!fs.existsSync(srcDir)) throw new Error(`Source directory not found: ${srcDir}`);
  if (!fs.existsSync(templatesDir)) throw new Error(`Templates directory not found: ${templatesDir}`);
  if (cleanOutDir && fs.existsSync(outDir)) {
    // basic clean
    fs.rmSync(outDir, { recursive: true, force: true });
  }
  ensureDir(outDir);

  const templates = loadTemplates(templatesDir);
  const pages = collectPages(srcDir, includeDrafts);
  const site = buildSiteData(pages, baseUrl);

  // Render pages using their layout
  for (const p of pages) {
    const html = renderWithLayout(templates.layouts, p.layout, { page: p, site, body: p.bodyHtml });
    const outFile = outputPathFor(outDir, p.url);
    const finalHtml = devServerPort ? injectLiveReload(html, devServerPort) : html;
    writeFileAtomic(outFile, finalHtml);
  }

  // Generate tag pages
  for (const [tag, taggedPages] of Object.entries(site.tags)) {
    const url = `/tags/${tag}/`;
    const outFile = outputPathFor(outDir, url);
    const html = renderTagPage(templates.layouts, tag, taggedPages, site);
    const finalHtml = devServerPort ? injectLiveReload(html, devServerPort) : html;
    writeFileAtomic(outFile, finalHtml);
  }

  // Write RSS
  const rss = generateRss(site);
  writeFileAtomic(path.join(outDir, 'rss.xml'), rss);

  // Copy static assets
  copyStaticAssets(srcDir, outDir);

  return { site, pages };
}
