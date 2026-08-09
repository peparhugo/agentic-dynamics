import path from 'node:path';
import fs from 'node:fs/promises';
import fg from 'fast-glob';
import matter from 'gray-matter';
import RSS from 'rss';
import { BuildOptions, Frontmatter, Page, TemplateRenderContext } from './types';
import { createMarkdown } from './markdown';
import { loadTemplates } from './templates';
import { ensureDirForFile, normalizeTags, outPathFor, parseDate, pickConcurrency, toUrlPath, writeFileEnsured } from './utils';

async function cleanDir(dir: string) {
  await fs.rm(dir, { recursive: true, force: true });
  await fs.mkdir(dir, { recursive: true });
}

export async function buildSite(opts: BuildOptions): Promise<{ pages: Page[]; tags: Map<string, Page[]>; }>
{
  const { srcDir, templatesDir, outDir, includeDrafts, baseUrl, liveReload } = opts;
  if (opts.clean) await cleanDir(outDir);

  const [templateEnv] = await Promise.all([
    loadTemplates(templatesDir),
    fs.mkdir(outDir, { recursive: true })
  ]);

  const files = await fg(['**/*.md'], { cwd: srcDir, dot: false });
  const md = createMarkdown();
  const concurrency = pickConcurrency(opts.concurrency);

  // Parallel render pages
  const results: Page[] = [];
  let idx = 0;
  async function worker() {
    while (idx < files.length) {
      const my = idx++;
      const relPath = files[my];
      if (!relPath) break;
      const srcPath = path.join(srcDir, relPath);
      const raw = await fs.readFile(srcPath, 'utf8');
      const parsed = matter(raw);
      const fmRaw = parsed.data as Frontmatter;
      const draft = Boolean(fmRaw.draft);
      if (draft && !includeDrafts) continue;
      const title = String(fmRaw.title || path.parse(relPath).name);
      const date = parseDate(fmRaw.date);
      const tags = normalizeTags(fmRaw.tags);

      const contentHtml = md.render(parsed.content);
      const urlPath = toUrlPath(relPath);
      const outPath = outPathFor(relPath, outDir);
      const page: Page = {
        srcPath,
        relPath,
        outPath,
        urlPath,
        content: contentHtml,
        fm: { ...fmRaw, title, date, tags, draft }
      };
      results.push(page);
    }
  }

  await Promise.all(Array.from({ length: concurrency }, () => worker()));

  // Sort pages by date desc (fallback to name)
  results.sort((a, b) => {
    const ad = a.fm.date?.getTime?.() ?? 0;
    const bd = b.fm.date?.getTime?.() ?? 0;
    if (bd !== ad) return bd - ad;
    return a.fm.title.localeCompare(b.fm.title);
  });

  // Build tag index
  const tagMap = new Map<string, Page[]>();
  for (const p of results) {
    for (const t of p.fm.tags || []) {
      const key = t.toLowerCase();
      const arr = tagMap.get(key) || [];
      arr.push(p);
      tagMap.set(key, arr);
    }
  }

  // Write pages using templates
  await Promise.all(results.map(async (page) => {
    const layout = String(page.fm.layout || templateEnv.defaultLayout);
    const ctx: TemplateRenderContext = {
      page,
      pages: results,
      tags: tagMap,
      site: { baseUrl, liveReload },
      content: page.content
    };
    const html = templateEnv.renderPage(layout, ctx);
    await writeFileEnsured(page.outPath, html);
  }));

  // Generate tag pages
  await Promise.all(Array.from(tagMap.entries()).map(async ([tag, pages]) => {
    const rel = path.join('tags', tag, 'index.html');
    const outPath = path.join(outDir, rel);
    const dummyPage: Page = {
      srcPath: '',
      relPath: rel,
      outPath,
      urlPath: '/tags/' + tag + '/',
      content: '',
      fm: { title: `Tag: ${tag}`, tags: [tag] }
    } as any;
    const ctx: TemplateRenderContext = {
      page: dummyPage,
      pages: results,
      tags: tagMap,
      site: { baseUrl, liveReload },
      content: ''
    };
    // layout "tags" fallback to default
    let html: string;
    try {
      html = templateEnv.renderPage('tags', ctx);
    } catch {
      html = templateEnv.renderPage(templateEnv.defaultLayout, ctx);
    }
    await writeFileEnsured(outPath, html);
  }));

  // RSS feed
  if (baseUrl) {
    const feed = new RSS({
      title: 'Site Feed',
      feed_url: new URL('/feed.xml', baseUrl).toString(),
      site_url: baseUrl
    });
    for (const p of results) {
      feed.item({
        title: p.fm.title,
        url: new URL(p.urlPath, baseUrl).toString(),
        date: p.fm.date || new Date(),
        categories: p.fm.tags
      });
    }
    const xml = feed.xml({ indent: true });
    await writeFileEnsured(path.join(outDir, 'feed.xml'), xml);
  }

  // Live reload client script if requested
  if (liveReload) {
    const js = `// injected live reload client\n(function(){\n  var wsProtocol = location.protocol === 'https:' ? 'wss' : 'ws';\n  var url = wsProtocol + '://' + location.host + '/_livereload';\n  function connect(){\n    var ws = new WebSocket(url);\n    ws.onmessage = function(ev){\n      if (ev.data === 'reload') { location.reload(); }\n    };\n    ws.onclose = function(){ setTimeout(connect, 1000); };\n  }\n  connect();\n})();\n`;
    await writeFileEnsured(path.join(outDir, '_livereload.js'), js);
  }

  return { pages: results, tags: tagMap };
}
