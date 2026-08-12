import fs from 'fs';
import path from 'path';
import matter from 'gray-matter';
import { marked } from 'marked';
import { Frontmatter, Page } from './types';

function normalizeTag(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.map((tag) => String(tag).trim()).filter(Boolean);
  }
  if (typeof value === 'string') {
    return value
      .split(',')
      .map((tag) => tag.trim())
      .filter(Boolean);
  }
  return [];
}

function normalizeTitle(fm: Frontmatter, filePath: string): string {
  if (typeof fm.title === 'string' && fm.title.trim()) {
    return fm.title.trim();
  }
  return path.basename(filePath, path.extname(filePath));
}

function normalizeDate(fm: Frontmatter): string {
  const value = fm.date;
  if (value instanceof Date && !Number.isNaN(value.getTime())) {
    return value.toISOString().slice(0, 10);
  }
  if (typeof value === 'string' && value.trim()) {
    return value.trim();
  }
  return '';
}

function toSlug(sourcePath: string, baseDir?: string): string {
  let relative = baseDir ? path.relative(baseDir, sourcePath) : path.basename(sourcePath);
  relative = relative.replace(/\\/g, '/');
  const parsed = path.parse(relative);
  const base = parsed.name === 'index' ? '' : parsed.name;
  const dir = parsed.dir ? `${parsed.dir}/` : '';
  return `${dir}${base}`.replace(/\/+$/, '') || 'index';
}

export function parseMarkdownFile(filePath: string, baseDir?: string): Page {
  const raw = fs.readFileSync(filePath, 'utf8');
  const { data, content } = matter(raw);
  const fm = (data || {}) as Frontmatter;

  const html = marked.parse(content) as string;

  return {
    sourcePath: filePath,
    slug: toSlug(filePath, baseDir),
    title: normalizeTitle(fm, filePath),
    date: normalizeDate(fm),
    tags: normalizeTag(fm.tags),
    content,
    html,
  };
}

export function escapeHtml(input: string): string {
  return input
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
