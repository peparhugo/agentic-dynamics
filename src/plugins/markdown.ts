import fs from 'node:fs/promises';
import path from 'node:path';
import { marked } from 'marked';
import { parseMarkdown } from '../parser';
import { Page, Plugin } from '../plugin';

function escapeHtml(value: unknown): string {
  return String(value ?? '').replace(/[&<>"']/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[character] as string));
}

export class MarkdownPlugin implements Plugin {
  async onFile(page: Page): Promise<void> {
    const parsed = parseMarkdown(await fs.readFile(page.source, 'utf8'));
    const title = typeof parsed.data.title === 'string'
      ? parsed.data.title : path.basename(page.url, '.html');
    const tags = Array.isArray(parsed.data.tags) ? parsed.data.tags : [];
    const metadata = [
      parsed.data.date ? `<time>${escapeHtml(parsed.data.date)}</time>` : '',
      tags.length ? `<p class="tags">${tags.map(escapeHtml).join(', ')}</p>` : '',
    ].join('');
    const html = marked.parse(parsed.content);
    page.data = parsed.data;
    page.content = parsed.content;
    page.html = html;
    page.body = `<article>\n<h1>${escapeHtml(title)}</h1>\n${metadata}\n${html}\n</article>`;
  }
}

export default MarkdownPlugin;
