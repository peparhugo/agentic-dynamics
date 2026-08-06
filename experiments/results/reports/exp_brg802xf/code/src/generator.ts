import path from 'node:path';
import fs from 'node:fs/promises';
import fg from 'fast-glob';
import matter from 'gray-matter';
import { createMarkdown } from './markdown';
import { loadTemplates } from './templates';
import { Frontmatter, GenerateOptions, Page } from './types';
import { generateRss } from './rss';

export async function generateSite(opts: GenerateOptions): Promise<{ pages: Page[]; tags: Map<string, Page[]>; }> {
  await fs.mkdir(opts.outDir, { recursive: true });
  const md = createMarkdown();
  const templates = await loadTemplates(opts.templatesDir);

  const mdFiles = await fg('**/*.md', { cwd: opts.srcDir, dot: false, onlyFiles: true });

  const pages: Page[] = [];
  for (const rel of mdFiles) {
    const full = path.join(opts.srcDir, rel);
    const raw = await fs.readFile(full, 'utf8');
    const parsed = matter(raw);
    const fm = normalizeFrontmatter(parsed.data as Frontmatter);
    if (fm.draft && !opts.includeDrafts) continue;

    const contentHtml = md.render(parsed.content);

    // Build URL and out paths: use directory with index.html
    const relNoExt = rel.replace(/\.md$/i, '');
    const outDir = path.join(opts.outDir, relNoExt);
    const urlPath = `/${relNoExt.replace(/\\/g, '/')}/`;
    await fs.mkdir(outDir, { recursive: true });

    // Render page template first
    const bodyHtml = templates.renderPage(fm.template || 'page', {
      ...fm,
      content: contentHtml,
      url: urlPath
    });

    // Wrap with layout
    let html = templates.renderWithLayout({ ...fm, body: bodyHtml, content: contentHtml, url: urlPath }, { layout: fm.layout || 'default' });

    if (opts.devInjectReload) {
      html = injectReload(html);
    }

    const outFile = path.join(outDir, 'index.html');
    await fs.writeFile(outFile, html, 'utf8');

    pages.push({ sourcePath: full, relPath: rel, outDir, urlPath, contentHtml, fm });
  }

  // Build tag pages
  const tagMap = buildTags(pages);
  await writeTagPages(tagMap, opts, templates);

  // Write RSS
  const rss = generateRss(pages, opts.siteUrl);
  await fs.writeFile(path.join(opts.outDir, 'rss.xml'), rss, 'utf8');

  return { pages, tags: tagMap };
}

function normalizeFrontmatter(fm: Frontmatter): Frontmatter {
  const out: Frontmatter = { ...fm };
  if (typeof out.tags === 'string') {
    out.tags = out.tags.split(',').map(s => s.trim()).filter(Boolean);
  }
  if (out.tags && !Array.isArray(out.tags)) {
    out.tags = [];
  }
  if (out.draft == null) out.draft = false;
  return out;
}

function buildTags(pages: Page[]): Map<string, Page[]> {
  const map = new Map<string, Page[]>();
  for (const p of pages) {
    const tags = p.fm.tags || [];
    for (const t of tags) {
      const arr = map.get(t) || [];
      arr.push(p);
      map.set(t, arr);
    }
  }
  // sort each by date desc
  for (const [k, arr] of map.entries()) {
    arr.sort((a, b) => (new Date(b.fm.date || 0).getTime()) - (new Date(a.fm.date || 0).getTime()));
    map.set(k, arr);
  }
  return map;
}

async function writeTagPages(tags: Map<string, Page[]>, opts: GenerateOptions, templates: Awaited<ReturnType<typeof loadTemplates>>) {
  const tagsRoot = path.join(opts.outDir, 'tags');
  await fs.mkdir(tagsRoot, { recursive: true });
  // index of tags
  const tagList = Array.from(tags.keys()).sort();
  let indexBody = templates.renderPage('tags-index', { tags: tagList });
  let indexHtml = templates.renderWithLayout({ title: 'Tags', body: indexBody }, { layout: 'default' });
  if (opts.devInjectReload) indexHtml = injectReload(indexHtml);
  await fs.writeFile(path.join(tagsRoot, 'index.html'), indexHtml, 'utf8');

  for (const tag of tagList) {
    const dir = path.join(tagsRoot, tag);
    await fs.mkdir(dir, { recursive: true });
    let body = templates.renderPage('tag', { tag, pages: tags.get(tag)!.map(p => ({ title: p.fm.title || p.urlPath, url: p.urlPath, date: p.fm.date })) });
    let html = templates.renderWithLayout({ title: `Tag: ${tag}`, body }, { layout: 'default' });
    if (opts.devInjectReload) html = injectReload(html);
    await fs.writeFile(path.join(dir, 'index.html'), html, 'utf8');
  }
}

function injectReload(html: string): string {
  const snippet = `<script>(function(){try{var p=location.protocol==='https:'?'wss':'ws';var ws=new WebSocket(p+'://'+location.host+'/__livereload');ws.onmessage=function(){location.reload()};}catch(e){console&&console.warn&&console.warn('livereload failed',e)}})();</script>`;
  if (/(<\/body>)/i.test(html)) return html.replace(/<\/body>/i, `${snippet}</body>`);
  return html + snippet;
}
