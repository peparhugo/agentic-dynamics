import { mkdirSync, writeFileSync, cpSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { Post, SiteConfig } from './types';
import { parseDirectory } from './parser';
import { Renderer } from './renderer';
import { writeRSS } from './rss';

function ensureDir(dir: string): void {
  if (!existsSync(dir)) {
    mkdirSync(dir, { recursive: true });
  }
}

function getLiveReloadScript(port: number): string {
  return `<script>
(function(){var w=new WebSocket('ws://localhost:${port}/__livereload');w.onmessage=function(e){if(e.data==='reload')location.reload();};})();
</script>`;
}

export function generate(config: SiteConfig, injectLiveReload = false): void {
  ensureDir(config.outputDir);

  let posts = parseDirectory(config.sourceDir);
  if (!config.includeDrafts) {
    posts = posts.filter((p) => !p.draft);
  }
  posts.sort((a, b) => b.date.getTime() - a.date.getTime());

  const renderer = new Renderer(config.templateDir);
  const reloadSnippet = injectLiveReload ? getLiveReloadScript(config.port) : '';

  for (const post of posts) {
    const html = renderer.renderPost(post, config) + reloadSnippet;
    const outDir = join(config.outputDir, post.slug);
    ensureDir(outDir);
    writeFileSync(join(outDir, 'index.html'), html, 'utf-8');
  }

  const tagMap = new Map<string, Post[]>();
  for (const post of posts) {
    for (const tag of post.tags) {
      if (!tagMap.has(tag)) tagMap.set(tag, []);
      tagMap.get(tag)!.push(post);
    }
  }

  for (const [tag, tagPosts] of tagMap) {
    const tagSlug = tag.toLowerCase().replace(/[^a-z0-9]+/g, '-');
    const html =
      renderer.renderTagPage(tag, tagPosts, config) + reloadSnippet;
    const outDir = join(config.outputDir, 'tags', tagSlug);
    ensureDir(outDir);
    writeFileSync(join(outDir, 'index.html'), html, 'utf-8');
  }

  const indexHtml = renderer.renderIndex(posts, config) + reloadSnippet;
  ensureDir(config.outputDir);
  writeFileSync(join(config.outputDir, 'index.html'), indexHtml, 'utf-8');

  writeRSS(posts, config);

  const assetsDir = join(config.templateDir, 'assets');
  if (existsSync(assetsDir)) {
    cpSync(assetsDir, join(config.outputDir, 'assets'), {
      recursive: true,
    });
  }
}
