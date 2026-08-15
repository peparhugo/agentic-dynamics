/**
 * Markdown → HTML rendering using `marked`.
 */

import { marked } from 'marked';

/**
 * Render a Markdown string to HTML using GitHub-flavoured Markdown.
 */
export function markdownToHtml(markdown: string): string {
  const result = marked.parse(markdown, {
    gfm: true,
    breaks: true,
  });
  return typeof result === 'string' ? result : markdown;
}
