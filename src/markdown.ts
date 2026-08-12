import fs from 'fs';
import path from 'path';
import MarkdownIt from 'markdown-it';
import matter from 'gray-matter';
import { Page } from './types';

const md = new MarkdownIt({ html: true, linkify: true, typographer: true });

export function slugify(input: string): string {
  const slug = input
    .toLowerCase()
    .trim()
    .replace(/[^\w\s-]/g, '')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '');
  return slug || 'untitled';
}

function stripHtml(html: string): string {
  return html.replace(/<[^>]+>/g, ' ');
}

function formatDate(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

export function parseMarkdown(content: string, filePath: string): Page {
  const { data, content: body } = matter(content);

  const rawTitle = typeof data.title === 'string' ? data.title : '';
  const title = rawTitle.trim()
    ? rawTitle.trim()
    : path.basename(filePath, path.extname(filePath));

  const rawDate =
    data.date instanceof Date
      ? formatDate(data.date)
      : typeof data.date === 'string'
        ? data.date
        : undefined;

  const rawTags = data.tags;
  const tags = Array.isArray(rawTags)
    ? rawTags.filter((t): t is string => typeof t === 'string')
    : [];

  const rawSlug = typeof data.slug === 'string' ? data.slug : '';
  const slug = slugify(rawSlug.trim() ? rawSlug : title);

  const html = md.render(body);
  const excerpt = stripHtml(html).trim().replace(/\s+/g, ' ').slice(0, 200);

  return {
    title,
    slug,
    date: rawDate,
    tags,
    body,
    html,
    excerpt,
    filePath,
  };
}
