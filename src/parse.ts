import fs from 'fs';
import path from 'path';
import matter from 'gray-matter';
import { marked } from 'marked';
import { Page, PageData } from './types';

function slugify(filePath: string): string {
  const base = path.basename(filePath, path.extname(filePath));
  const slug = base
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
  return slug || 'page';
}

function toTags(raw: unknown): string[] | undefined {
  if (!raw) return undefined;
  if (Array.isArray(raw)) return raw.map((t) => String(t));
  return String(raw)
    .split(',')
    .map((t) => t.trim())
    .filter((t) => t.length > 0);
}

function toDate(raw: unknown): string | undefined {
  if (typeof raw === 'string') return raw;
  if (raw instanceof Date) return raw.toISOString().slice(0, 10);
  return undefined;
}

function toData(frontmatter: Record<string, unknown>): PageData {
  return {
    title: typeof frontmatter.title === 'string' ? frontmatter.title : undefined,
    date: toDate(frontmatter.date),
    tags: toTags(frontmatter.tags),
    template: typeof frontmatter.template === 'string' ? frontmatter.template : undefined,
    layout: typeof frontmatter.layout === 'string' ? frontmatter.layout : undefined,
  };
}

export function parseMarkdown(filePath: string): Page {
  const raw = fs.readFileSync(filePath, 'utf-8');
  const { content, data } = matter(raw);
  const html = marked.parse(content, { async: false }) as string;
  return {
    slug: slugify(filePath),
    content,
    html,
    data: toData(data),
  };
}
