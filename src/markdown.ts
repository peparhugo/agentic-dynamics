import { marked } from 'marked';

export async function markdownToHtml(markdown: string): Promise<string> {
  const html = await marked.parse(markdown);
  return html.trim();
}
