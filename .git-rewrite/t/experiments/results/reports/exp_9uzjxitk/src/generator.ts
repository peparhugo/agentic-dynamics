import fs from 'node:fs';
import path from 'node:path';
import { parseAll } from './parser.js';
import { loadTemplates, renderPage } from './renderer.js';
import { generateRSS } from './rss.js';
import type { Post, SiteConfig, TemplateContext } from './types.js';

const RELOAD_SCRIPT = `
<script>
  (function() {
    var ws = new WebSocket('ws://' + location.host + '/__reload');
    ws.onmessage = function(msg) {
      if (msg.data === 'reload') location.reload();
    };
  })();
</script>`;

export function generate(config: SiteConfig, injectReload: boolean = false): void {
  fs.mkdirSync(config.output, { recursive: true });

  const posts = parseAll(config.src);
  const published = posts.filter((p) => !p.frontmatter.draft);
  const templates = loadTemplates(config.templates);

  for (const post of published) {
    const ctx: TemplateContext = {
      title: post.frontmatter.title,
      posts: published,
      tags: buildTagIndex(published),
      site: { title: config.siteTitle, description: config.siteDescription, baseUrl: config.baseUrl },
      page: post,
    };

    let html = renderPage(templates, 'post', ctx);
    if (injectReload) html += RELOAD_SCRIPT;

    const outPath = path.join(config.output, `${post.slug}.html`);
    fs.mkdirSync(path.dirname(outPath), { recursive: true });
    fs.writeFileSync(outPath, html);
  }

  const indexCtx: TemplateContext = {
    title: config.siteTitle,
    posts: published,
    tags: buildTagIndex(published),
    site: { title: config.siteTitle, description: config.siteDescription, baseUrl: config.baseUrl },
  };

  let indexHtml = renderPage(templates, 'index', indexCtx);
  if (injectReload) indexHtml += RELOAD_SCRIPT;
  fs.writeFileSync(path.join(config.output, 'index.html'), indexHtml);

  const tagIndex = buildTagIndex(published);
  for (const { tag, posts: tagPosts } of tagIndex) {
    const tagCtx: TemplateContext = {
      title: `Posts tagged "${tag}"`,
      posts: tagPosts,
      tags: tagIndex,
      site: { title: config.siteTitle, description: config.siteDescription, baseUrl: config.baseUrl },
    };

    let tagHtml = renderPage(templates, 'tag', tagCtx);
    if (injectReload) tagHtml += RELOAD_SCRIPT;

    const tagDir = path.join(config.output, 'tags', encodeURIComponent(tag));
    fs.mkdirSync(tagDir, { recursive: true });
    fs.writeFileSync(path.join(tagDir, 'index.html'), tagHtml);
  }

  const rssXml = generateRSS(published, config);
  fs.writeFileSync(path.join(config.output, 'rss.xml'), rssXml);

  if (templates.layouts['default'] && !injectReload) {
    copyAssets(config.templates, config.output);
  }
}

function buildTagIndex(posts: Post[]): Array<{ tag: string; posts: Post[] }> {
  const map = new Map<string, Post[]>();
  for (const post of posts) {
    if (post.frontmatter.draft) continue;
    for (const tag of post.frontmatter.tags) {
      if (!map.has(tag)) map.set(tag, []);
      map.get(tag)!.push(post);
    }
  }
  return [...map.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([tag, posts]) => ({ tag, posts }));
}

function copyAssets(srcDir: string, outDir: string): void {
  const exclude = new Set(['.hbs', '.handlebars']);
  function walk(dir: string) {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      const relative = path.relative(srcDir, full);
      const dest = path.join(outDir, relative);
      if (entry.isDirectory() && entry.name !== 'layouts' && entry.name !== 'partials') {
        fs.mkdirSync(dest, { recursive: true });
        walk(full);
      } else if (entry.isFile() && !exclude.has(path.extname(entry.name))) {
        fs.mkdirSync(path.dirname(dest), { recursive: true });
        fs.copyFileSync(full, dest);
      }
    }
  }
  walk(srcDir);
}
