import { parseFrontmatter, Frontmatter } from './frontmatter';
import { markdownToHtml } from './markdown';

export interface PageData {
  title: string;
  date?: string;
  tags?: string[];
  html: string;
  slug: string;
  template?: string;
  layout?: string;
  [key: string]: unknown;
}

export async function processMarkdownFile(filename: string, content: string): Promise<PageData> {
  const { data, content: markdownContent } = parseFrontmatter(content);
  const html = await markdownToHtml(markdownContent);
  const slug = filename.replace(/\.md$/, '');

  const title = (data.title as string) || slug.split('-').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');

  return {
    slug,
    title,
    date: data.date as string | undefined,
    tags: Array.isArray(data.tags) ? data.tags : undefined,
    html,
    ...data
  };
}
