import matter from 'gray-matter';
import { marked } from 'marked';
import * as path from 'path';
import { FrontMatter, Page } from './types';

marked.setOptions({ gfm: true });

/**
 * Turns a source-relative markdown path into a title-cased fallback title,
 * used when a page has no frontmatter title.
 */
function titleFromSlug(slug: string): string {
  const base = slug.split('/').pop() || slug;
  return base
    .replace(/[-_]+/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function normalizeTags(rawTags: unknown): string[] {
  if (Array.isArray(rawTags)) {
    return rawTags.map((t) => String(t));
  }
  if (typeof rawTags === 'string' && rawTags.trim().length > 0) {
    return rawTags.split(',').map((t) => t.trim());
  }
  return [];
}

function normalizeDate(rawDate: unknown): string | undefined {
  if (rawDate === undefined || rawDate === null) return undefined;
  if (rawDate instanceof Date) return rawDate.toISOString().slice(0, 10);
  return String(rawDate);
}

/**
 * Parses a single markdown file's raw text (with optional frontmatter) into
 * a Page. `relativePath` is the file's path relative to the content
 * directory, using forward slashes, e.g. "posts/hello-world.md".
 */
export function parseMarkdown(raw: string, relativePath: string): Page {
  const { data, content } = matter(raw);
  const frontMatter = data as FrontMatter;

  const parsedPath = path.posix.parse(relativePath.split(path.sep).join('/'));
  const slug = parsedPath.dir ? `${parsedPath.dir}/${parsedPath.name}` : parsedPath.name;

  const html = marked.parse(content, { async: false }) as string;

  return {
    sourcePath: relativePath,
    slug,
    outputFile: `${slug}.html`,
    title: frontMatter.title ? String(frontMatter.title) : titleFromSlug(slug),
    date: normalizeDate(frontMatter.date),
    tags: normalizeTags(frontMatter.tags),
    html,
    template: frontMatter.template ? String(frontMatter.template) : undefined,
  };
}
