import { readFileSync, readdirSync, statSync } from 'fs';
import { join, extname, basename } from 'path';
import yaml from 'js-yaml';
import { Marked } from 'marked';
import { Frontmatter, Post } from './types';
import { highlightCode } from './highlight';

const marked = new Marked();

marked.use({
  renderer: {
    code({ text, lang }: { text: string; lang?: string }) {
      return highlightCode(text, lang);
    },
  },
});

export function parseFrontmatter(raw: string): { frontmatter: Frontmatter; body: string } {
  const match = raw.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/);
  if (!match) {
    throw new Error('No valid frontmatter found');
  }

  const parsed = yaml.load(match[1]);
  if (!parsed || typeof parsed !== 'object') {
    throw new Error('Invalid frontmatter YAML');
  }

  const fm = parsed as Record<string, unknown>;
  if (typeof fm.title !== 'string' || !fm.title.trim()) {
    throw new Error('Frontmatter must contain a non-empty title');
  }

  const frontmatter: Frontmatter = {
    title: fm.title,
    date: typeof fm.date === 'string' ? fm.date : undefined,
    tags: Array.isArray(fm.tags) ? fm.tags.map(String) : undefined,
    draft: typeof fm.draft === 'boolean' ? fm.draft : undefined,
    layout: typeof fm.layout === 'string' ? fm.layout : undefined,
  };

  for (const key of Object.keys(fm)) {
    if (!(key in frontmatter)) {
      frontmatter[key] = fm[key];
    }
  }

  return { frontmatter, body: match[2] };
}

export function parseMarkdown(raw: string): { frontmatter: Frontmatter; html: string } {
  const { frontmatter, body } = parseFrontmatter(raw);
  const html = marked.parse(body) as string;
  return { frontmatter, html };
}

function slugify(filename: string): string {
  return basename(filename, extname(filename))
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

export function collectMarkdownFiles(dir: string): string[] {
  const files: string[] = [];

  function walk(d: string) {
    for (const entry of readdirSync(d)) {
      const full = join(d, entry);
      const st = statSync(full);
      if (st.isDirectory()) {
        walk(full);
      } else if (extname(entry) === '.md') {
        files.push(full);
      }
    }
  }

  walk(dir);
  return files;
}

export function parsePosts(sourceDir: string): Post[] {
  const files = collectMarkdownFiles(sourceDir);
  const posts: Post[] = [];

  for (const file of files) {
    try {
      const raw = readFileSync(file, 'utf-8');
      const { frontmatter, html } = parseMarkdown(raw);
      if (frontmatter.draft) continue;

      const slug = slugify(file);
      posts.push({
        frontmatter,
        content: raw,
        html,
        slug,
        sourcePath: file,
      });
    } catch {
      // skip unparseable files
    }
  }

  posts.sort((a, b) => {
    const da = a.frontmatter.date ? new Date(a.frontmatter.date).getTime() : 0;
    const db = b.frontmatter.date ? new Date(b.frontmatter.date).getTime() : 0;
    return db - da;
  });

  return posts;
}
