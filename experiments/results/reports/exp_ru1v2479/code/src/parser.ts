import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative, basename } from 'node:path';
import matter from 'gray-matter';
import { Post } from './types';
import { getMarked } from './highlight';

function slugify(name: string): string {
  return basename(name, '.md')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');
}

function walkDir(dir: string, files: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      walkDir(full, files);
    } else if (entry.endsWith('.md')) {
      files.push(full);
    }
  }
  return files;
}

export function parseFile(filePath: string, sourceDir: string): Post {
  const raw = readFileSync(filePath, 'utf-8');
  const { data, content } = matter(raw);
  const html = getMarked().parse(content) as string;
  const rel = relative(sourceDir, filePath);

  return {
    slug: slugify(rel),
    title: data.title || slugify(rel),
    date: data.date ? new Date(data.date) : new Date(),
    tags: Array.isArray(data.tags) ? data.tags : [],
    draft: data.draft === true,
    content,
    html,
    layout: data.layout || 'default',
  };
}

export function parseDirectory(sourceDir: string): Post[] {
  const files = walkDir(sourceDir);
  return files.map((f) => parseFile(f, sourceDir));
}
