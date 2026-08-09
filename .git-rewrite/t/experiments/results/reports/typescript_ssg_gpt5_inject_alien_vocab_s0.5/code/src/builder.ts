import path from 'path';
import fs from 'fs';
import fg from 'fast-glob';
import { parseMarkdown } from './markdown';
import { loadTemplates } from './templates';
import { BuildOptions, Doc, SiteData } from './types';

function ensureDir(p: string) {
  fs.mkdirSync(p, { recursive: true });
}

function writeFile(p: string, content: string) {
  ensureDir(path.dirname(p));
  fs.writeFileSync(p, content);
}

function toUrl(outDir: string, outPath: string): string {
  const rel = path.relative(outDir, outPath).split(path.sep).join('/');
  return '/' + rel;
}

function htmlOutPath(srcDir: string, outDir: string, file: string): string {
  const rel = path.relative(srcDir, file);
  const outRel = rel.replace(/\.(md|markdown)$/i, '.html');
  return path.join(outDir, outRel);
}

function computeId(srcDir: string, file: string) {
  const rel = path.relative(srcDir, file);
  return rel.replace(/\.(md|markdown)$/i, '');
}

function inferIsPost(id: string, fm: any): boolean {
  if (typeof fm?.date !== 'undefined') return true;
  const parts = id.split(/[\\/]/);
  return parts.includes('posts');
}

function normalizeTags(val: unknown): string[] {
  if (!val) return [];
  if (Array.isArray(val)) return val.map(String).map((t) => t.trim()).filter(Boolean);
  if (typeof val === 'string') return val.split(',').map((t) => t.trim()).filter(Boolean);
  return [];
}

function injectLiveReload(html: string, port: number): string {
  const snippet = `\n<script>\n(function(){\n  var ws = new WebSocket('ws://'+location.hostname+':${port}/__livereload');\n  ws.onmessage = function(msg){ if(msg.data==='reload') location.reload(); };\n})();\n</script>\n`;
  if (html.includes('</body>')) return html.replace('</body>', snippet + '</body>');
  return html + snippet;
}

export async function buildSite(opts: BuildOptions & { liveReloadPort?: number }): Promise<SiteData> {
  const { srcDir, templatesDir, outDir, siteTitle, siteUrl, dev, liveReloadPort } = opts;
  const templates = loadTemplates(templatesDir);

  const mdFiles = await fg(['**/*.md', '**/*.markdown'], { cwd: srcDir, absolute: true });
  const docs: Doc[] = [];
  for (const file of mdFiles) {
    const raw = fs.readFileSync(file, 'utf8');
    const { frontmatter, contentHtml, rawBody } = parseMarkdown(raw);
    const id = computeId(srcDir, file);
    const outPath = htmlOutPath(srcDir, outDir, file);
    const url = toUrl(outDir, outPath);
    const title = (frontmatter.title as string) || path.basename(id).replace(/[-_]/g, ' ');
    const dateVal = frontmatter.date ? new Date(frontmatter.date as any) : undefined;
    const tags = normalizeTags(frontmatter.tags);
    const draft = Boolean(frontmatter.draft);
    const fm = { ...frontmatter, title, date: dateVal, tags, draft } as Doc['frontmatter'];
    const isPost = inferIsPost(id, fm);
    docs.push({ id, srcPath: file, outPath, url, frontmatter: fm, body: contentHtml, rawBody, isPost });
  }

  const published = docs.filter((d) => !d.frontmatter.draft);
  const posts = published.filter((d) => d.isPost).sort((a, b) => {
    const da = a.frontmatter.date?.getTime() || 0;
    const db = b.frontmatter.date?.getTime() || 0;
    return db - da;
  });
  const tags = new Map<string, Doc[]>();
  for (const d of posts) {
    for (const t of d.frontmatter.tags) {
      const key = t;
      const arr = tags.get(key) || [];
      arr.push(d);
      tags.set(key, arr);
    }
  }
  const site: SiteData = { title: siteTitle || 'Site', url: siteUrl, docs: published, posts, tags };

  // Render each doc using templates
  for (const d of published) {
    const templateName = (d.frontmatter.template as string) || 'page';
    const layoutName = (d.frontmatter.layout as string) || 'main';
    const ctx = { site, page: d, content: d.body, body: d.body, tags: Array.from(tags.keys()).sort() };
    let html = templates.renderPage(templateName, layoutName, ctx);
    if (dev && opts.liveReloadPort) html = injectLiveReload(html, opts.liveReloadPort);
    writeFile(d.outPath, html);
  }

  // Tag index pages
  if (tags.size > 0 && templates.hasTemplate('tag')) {
    for (const [tag, tagPosts] of tags.entries()) {
      const ctx = { site, tag, posts: tagPosts };
      let html = templates.renderPage('tag', 'main', ctx);
      if (dev && opts.liveReloadPort) html = injectLiveReload(html, opts.liveReloadPort);
      const outPath = path.join(opts.outDir, 'tags', tag, 'index.html');
      writeFile(outPath, html);
    }
  }

  // Tags list page if template exists
  if (tags.size > 0 && templates.hasTemplate('tags')) {
    const ctx = { site, tags: Array.from(tags.entries()).map(([name, posts]) => ({ name, count: posts.length })) };
    let html = templates.renderPage('tags', 'main', ctx);
    if (dev && opts.liveReloadPort) html = injectLiveReload(html, opts.liveReloadPort);
    writeFile(path.join(opts.outDir, 'tags', 'index.html'), html);
  }

  // RSS feed
  const rss = generateRSS(site);
  writeFile(path.join(outDir, 'rss.xml'), rss);

  return site;
}

function xmlEscape(s: string) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function absUrl(siteUrl: string | undefined, urlPath: string) {
  if (!siteUrl) return urlPath; // best effort
  return siteUrl.replace(/\/$/, '') + urlPath;
}

export function generateRSS(site: SiteData): string {
  const items = site.posts.slice(0, 20).map((p) => {
    const link = absUrl(site.url, p.url);
    const title = xmlEscape(p.frontmatter.title || '');
    const pubDate = p.frontmatter.date ? new Date(p.frontmatter.date).toUTCString() : new Date().toUTCString();
    const description = xmlEscape(stripHtml(p.body).slice(0, 500));
    return `\n    <item>\n      <title>${title}</title>\n      <link>${link}</link>\n      <guid>${link}</guid>\n      <pubDate>${pubDate}</pubDate>\n      <description>${description}</description>\n    </item>`;
  }).join('');

  const channelLink = site.url || '';
  return `<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0">\n  <channel>\n    <title>${xmlEscape(site.title)}</title>\n    <link>${xmlEscape(channelLink)}</link>\n    <description>${xmlEscape(site.title)}</description>${items}\n  </channel>\n</rss>\n`;
}

function stripHtml(html: string): string {
  return html.replace(/<[^>]*>/g, '');
}
