import matter from 'gray-matter';
import { marked } from 'marked';

export interface PageFrontmatter {
  title: string;
  date?: string;
  tags?: string[];
  template?: string;
  layout?: string;
  [key: string]: any;
}

export interface ParsedPage {
  frontmatter: PageFrontmatter;
  html: string;
  slug: string;
}

export async function parseMarkdown(content: string, slug: string): Promise<ParsedPage> {
  const { data, content: markdown } = matter(content);

  const frontmatter: PageFrontmatter = {
    title: data.title || 'Untitled',
    date: data.date,
    tags: data.tags || [],
    ...data,
  };

  const html = await marked(markdown);

  return {
    frontmatter,
    html,
    slug,
  };
}
