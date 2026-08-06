import { readFile, writeFile, mkdir, readdir } from 'fs/promises';
import { join, extname } from 'path';
import { readPost } from './frontmatter.js';
import { loadTemplates, registerHelpers, renderPage } from './renderer.js';
import { markdownToHtml, highlightCode, setupMarked } from './highlight.js';
import { BuildOptions, Post, SiteConfig } from './types.js';

interface FlatPost {
  title: string;
  date?: string;
  tags?: string[];
  draft?: boolean;
  slug: string;
  url: string;
  content: string;
  description: string;
}

function flattenPost(post: Post): FlatPost {
  return {
    title: post.frontmatter.title,
    date: post.frontmatter.date,
    tags: post.frontmatter.tags,
    draft: post.frontmatter.draft,
    slug: post.slug,
    url: post.url,
    content: post.html,
    description: post.description,
  };
}

async function findMarkdownFiles(dir: string): Promise<string[]> {
  const results: string[] = [];
  async function walk(current: string) {
    const entries = await readdir(current, { withFileTypes: true });
    for (const entry of entries) {
      const fullPath = join(current, entry.name);
      if (entry.isDirectory()) {
        await walk(fullPath);
      } else if (extname(entry.name) === '.md') {
        results.push(fullPath);
      }
    }
  }
  await walk(dir);
  return results;
}

async function loadSiteConfig(
  sourceDir: string,
  options: BuildOptions,
): Promise<SiteConfig> {
  const configPath = join(sourceDir, 'site.json');
  let fileConfig: Partial<SiteConfig> = {};
  try {
    const raw = await readFile(configPath, 'utf-8');
    fileConfig = JSON.parse(raw);
  } catch {
    // no site.json, use defaults
  }

  return {
    title: options.title || fileConfig.title || 'My Site',
    description: options.description || fileConfig.description || '',
    url: options.url || fileConfig.url || 'http://localhost:3000',
  };
}

export async function build(options: BuildOptions): Promise<void> {
  setupMarked();
  const site = await loadSiteConfig(options.source, options);
  registerHelpers(site);

  await mkdir(options.output, { recursive: true });

  const mdFiles = await findMarkdownFiles(options.source);

  let posts: Post[] = [];
  for (const filepath of mdFiles) {
    const post = await readPost(filepath);
    posts.push(post);
  }

  if (!options.includeDrafts) {
    posts = posts.filter((p) => !p.frontmatter.draft);
  }

  posts.sort((a, b) => {
    const da = a.frontmatter.date ? new Date(a.frontmatter.date).getTime() : 0;
    const db = b.frontmatter.date ? new Date(b.frontmatter.date).getTime() : 0;
    return db - da;
  });

  for (const post of posts) {
    const rawHtml = markdownToHtml(post.content);
    post.html = highlightCode(rawHtml);
  }

  const flatPosts = posts.map(flattenPost);

  const { templates, layout } = await loadTemplates(options.templates);

  for (const post of flatPosts) {
    const postDir = join(options.output, post.slug);
    await mkdir(postDir, { recursive: true });

    const html = renderPage(templates, layout, 'post', {
      site,
      posts: flatPosts,
      title: post.title,
      content: post.content,
      date: post.date,
      tags: post.tags,
      url: post.url,
      description: post.description,
    });

    await writeFile(join(postDir, 'index.html'), html);
  }

  const allTags = new Map<string, FlatPost[]>();
  for (const post of flatPosts) {
    if (post.tags) {
      for (const tag of post.tags) {
        if (!allTags.has(tag)) allTags.set(tag, []);
        allTags.get(tag)!.push(post);
      }
    }
  }

  for (const [tag, taggedPosts] of allTags) {
    const tagSlug = tag.toLowerCase().replace(/\s+/g, '-');
    const tagDir = join(options.output, 'tags', tagSlug);
    await mkdir(tagDir, { recursive: true });

    const html = renderPage(templates, layout, 'tag', {
      site,
      tag,
      posts: taggedPosts,
      title: `Tag: ${tag}`,
    });

    await writeFile(join(tagDir, 'index.html'), html);
  }

  if (templates.has('index')) {
    const html = renderPage(templates, layout, 'index', {
      site,
      posts: flatPosts,
      title: site.title,
    });
    await writeFile(join(options.output, 'index.html'), html);
  }

  if (templates.has('rss')) {
    const rssXml = renderPage(templates, layout, 'rss', {
      site,
      posts: flatPosts,
      title: site.title,
    });
    await writeFile(join(options.output, 'feed.xml'), rssXml);
  }
}
