import * as fs from 'fs';
import * as path from 'path';
import matter from 'gray-matter';
import { marked } from 'marked';
import { Page } from './types';

export function slugify(fileName: string): string {
  const base = fileName.replace(/\.md$/i, '');
  return base
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

export function titleFromSlug(slug: string): string {
  return slug
    .split('-')
    .filter(Boolean)
    .map((word) => word[0].toUpperCase() + word.slice(1))
    .join(' ');
}

export function normalizeDate(date: unknown): string {
  if (date instanceof Date) {
    return date.toISOString().slice(0, 10);
  }
  if (typeof date === 'string') {
    return date;
  }
  if (date === undefined || date === null) {
    return '';
  }
  return String(date);
}

export function normalizeTags(tags: unknown): string[] {
  if (Array.isArray(tags)) {
    return tags.map((tag) => String(tag).trim()).filter(Boolean);
  }
  if (typeof tags === 'string') {
    return tags
      .split(',')
      .map((tag) => tag.trim())
      .filter(Boolean);
  }
  return [];
}

export function parseMarkdownFile(filePath: string, contentDir: string): Page {
  const raw = fs.readFileSync(filePath, 'utf-8');
  const { data, content } = matter(raw);

  const relativePath = path.relative(contentDir, filePath);
  const fileName = path.basename(filePath);
  const slug = slugify(relativePath.replace(/\\/g, '/'));

  const title = typeof data.title === 'string' && data.title.trim() ? data.title.trim() : titleFromSlug(slugify(fileName));
  const date = normalizeDate(data.date);
  const tags = normalizeTags(data.tags);

  const html = marked.parse(content, { async: false }) as string;

  return {
    title,
    date,
    tags,
    slug,
    sourcePath: filePath,
    outputPath: `${slug}.html`,
    html,
  };
}

export function findMarkdownFiles(dir: string): string[] {
  if (!fs.existsSync(dir)) {
    return [];
  }
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  const files: string[] = [];
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...findMarkdownFiles(fullPath));
    } else if (entry.isFile() && /\.md$/i.test(entry.name)) {
      files.push(fullPath);
    }
  }
  return files.sort();
}
