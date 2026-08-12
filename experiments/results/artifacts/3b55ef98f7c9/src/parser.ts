import fs from 'fs';
import path from 'path';
import matter from 'gray-matter';
import { marked } from 'marked';
import { Page, Frontmatter } from './types';

export function parseMarkdownFile(filePath: string): Page {
  const raw = fs.readFileSync(filePath, 'utf-8');
  const parsed = matter(raw);
  const data = parsed.data as Record<string, unknown>;
  const frontmatter: Frontmatter = {
    title: data.title as string,
    date: data.date instanceof Date ? (data.date as Date).toISOString().slice(0, 10) : data.date != null ? String(data.date) : undefined,
    tags: data.tags as string[] | undefined,
    template: data.template as string | undefined,
    layout: data.layout as string | undefined,
  };

  if (!frontmatter.title) {
    throw new Error(`Missing required frontmatter field "title" in ${filePath}`);
  }

  const html = marked.parse(parsed.content) as string;
  const slug = path.basename(filePath, path.extname(filePath));

  return {
    frontmatter,
    content: parsed.content,
    html,
    slug,
    sourcePath: filePath,
  };
}

export function parseMarkdownDirectory(
  contentDir: string,
): Page[] {
  if (!fs.existsSync(contentDir)) {
    throw new Error(`Content directory not found: ${contentDir}`);
  }

  const entries = fs.readdirSync(contentDir);
  const pages: Page[] = [];

  for (const entry of entries) {
    const fullPath = path.join(contentDir, entry);
    const stat = fs.statSync(fullPath);
    if (stat.isFile() && (entry.endsWith('.md') || entry.endsWith('.markdown'))) {
      pages.push(parseMarkdownFile(fullPath));
    }
  }

  return pages.sort((a, b) => {
    const dateA = a.frontmatter.date || '';
    const dateB = b.frontmatter.date || '';
    return dateB.localeCompare(dateA);
  });
}
