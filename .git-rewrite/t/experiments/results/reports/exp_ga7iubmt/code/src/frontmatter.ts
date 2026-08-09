import { readFile } from 'fs/promises';
import { basename, extname } from 'path';
import matter from 'gray-matter';
import { Frontmatter, Post } from './types.js';

export function slugify(filename: string): string {
  return basename(filename, extname(filename))
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');
}

export function parseFrontmatter(raw: string, filename: string): {
  frontmatter: Frontmatter;
  content: string;
} {
  const parsed = matter(raw);
  const fm = parsed.data as Record<string, unknown>;
  return {
    frontmatter: {
      title: (fm.title as string) || slugify(filename),
      date: fm.date as string | undefined,
      tags: Array.isArray(fm.tags) ? fm.tags.map(String) : undefined,
      draft: fm.draft === true || fm.draft === 'true',
    },
    content: parsed.content,
  };
}

export async function readPost(filepath: string): Promise<Post> {
  const raw = await readFile(filepath, 'utf-8');
  const { frontmatter, content } = parseFrontmatter(raw, filepath);
  const slug = slugify(filepath);
  return {
    frontmatter,
    content,
    html: '', // populated later by renderer
    slug,
    url: `/${slug}/`,
    description: content.slice(0, 200).replace(/\n/g, ' ').trim(),
  };
}
