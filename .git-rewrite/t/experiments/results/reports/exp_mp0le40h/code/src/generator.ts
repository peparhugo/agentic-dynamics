import { join } from 'path';
import { parsePosts } from './parser';
import { loadTemplates, renderPage, renderIndex, renderTagPage } from './renderer';
import { writeFile, copyStaticFiles, ensureDir } from './utils';
import { Post, SiteConfig } from './types';
import { generateRSS } from './rss';

export interface GenerateOptions {
  silent?: boolean;
  isDev?: boolean;
}

export function generate(config: SiteConfig, options: GenerateOptions = {}): void {
  const { source, output, templates: templatesDir } = config;
  const { silent = false, isDev = false } = options;

  const posts = parsePosts(source);
  const templates = loadTemplates(templatesDir);

  ensureDir(output);

  copyStaticFiles(source, output);

  if (!silent && !isDev) {
    console.log(`Found ${posts.length} posts`);
  }

  const indexHtml = renderIndex(templates, posts, config, isDev);
  writeFile(join(output, 'index.html'), indexHtml);

  for (const post of posts) {
    const html = renderPage(templates, post, config, posts, isDev);
    const outDir = join(output, post.slug);
    writeFile(join(outDir, 'index.html'), html);
  }

  const tagMap = new Map<string, Post[]>();
  for (const post of posts) {
    for (const tag of post.frontmatter.tags || []) {
      if (!tagMap.has(tag)) tagMap.set(tag, []);
      tagMap.get(tag)!.push(post);
    }
  }

  ensureDir(join(output, 'tags'));
  for (const [tag, tagPosts] of tagMap) {
    const html = renderTagPage(templates, tag, tagPosts, config, isDev);
    writeFile(join(output, 'tags', tag, 'index.html'), html);
  }

  const rss = generateRSS(posts, config);
  writeFile(join(output, 'rss.xml'), rss);

  if (!silent && !isDev) {
    console.log(`Generated site to ${output}`);
  }
}
