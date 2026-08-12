import { readFileSync } from 'fs';
import { basename, extname } from 'path';
import { parseMarkdown } from './markdown';

export interface Page {
  slug: string;
  title: string;
  date: string;
  tags: string[];
  contentHtml: string;
}

export function pageFromFile(filePath: string): Page {
  const raw = readFileSync(filePath, 'utf8');
  const parsed = parseMarkdown(raw);
  const slug = basename(filePath, extname(filePath));
  return {
    slug,
    title: parsed.frontmatter.title ?? slug,
    date: parsed.frontmatter.date ?? '',
    tags: parsed.frontmatter.tags ?? [],
    contentHtml: parsed.contentHtml,
  };
}
