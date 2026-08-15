import MarkdownIt from 'markdown-it';

const md = new MarkdownIt();

export function markdownToHtml(markdown: string): string {
  return md.render(markdown).trim();
}
