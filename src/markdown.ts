import { marked } from 'marked';

export function markdownToHtml(markdown: string): string {
  return marked(markdown) as string;
}
