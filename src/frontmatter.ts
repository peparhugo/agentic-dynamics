import matter from 'gray-matter';
import type { Frontmatter } from './types';

export interface ParsedMarkdown {
  content: string;
  data: Frontmatter;
}

export function parseFrontmatter(fileContents: string): ParsedMarkdown {
  const result = matter(fileContents);
  return {
    content: result.content,
    data: (result.data || {}) as Frontmatter
  };
}

export function extractTags(data: Frontmatter): string[] {
  const raw = data.tags;
  if (!Array.isArray(raw)) return [];
  return raw.filter((tag): tag is string => typeof tag === 'string');
}
