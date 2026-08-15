import { marked } from 'marked';
import { parseFrontmatter } from './frontmatter';
import type { ParsedMarkdown } from './types';

marked.setOptions({
  gfm: true,
  breaks: false,
});

/**
 * Render a markdown string to HTML and return the parsed frontmatter data.
 */
export function renderMarkdownToHtml(markdown: string): ParsedMarkdown & { html: string } {
  const { data, content } = parseFrontmatter(markdown);
  const html = marked.parse(content, { async: false }) as string;
  return { data, content, html };
}
