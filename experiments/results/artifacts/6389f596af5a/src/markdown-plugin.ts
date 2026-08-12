import { promises as fs } from 'node:fs';
import matter from 'gray-matter';
import { marked } from 'marked';
import type { Page } from './generator';
import type { Plugin, PluginContext } from './plugin';

type Frontmatter = { title?: unknown; date?: unknown; tags?: unknown; template?: unknown; layout?: unknown };
type SourcePage = Page & { filePath?: string; frontmatter?: Frontmatter };

function metadataValue(value: unknown): string | undefined {
  return value instanceof Date ? value.toISOString().slice(0, 10) :
    typeof value === 'string' || typeof value === 'number' ? String(value) : undefined;
}

function tagsValue(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String);
  if (typeof value === 'string') return value.split(',').map((tag) => tag.trim()).filter(Boolean);
  return [];
}

function templateValue(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim() ? value.trim() : undefined;
}

export class MarkdownPlugin implements Plugin {
  async onFile(page: Page, _context: PluginContext): Promise<Page> {
    const source = page as SourcePage;
    if (!source.filePath) return page;
    const parsed = matter(await fs.readFile(source.filePath, 'utf8'));
    const metadata = parsed.data as Frontmatter;
    const title = metadataValue(metadata.title) ?? page.title;
    const date = metadataValue(metadata.date);
    const tags = tagsValue(metadata.tags);
    const template = templateValue(metadata.template);
    const layout = templateValue(metadata.layout);
    const content = await marked.parse(parsed.content);
    const details = [date ? `<time datetime="${escapeHtml(date)}">${escapeHtml(date)}</time>` : '',
      tags.length ? `<ul class="tags">${tags.map((tag) => `<li>${escapeHtml(tag)}</li>`).join('')}</ul>` : '']
      .filter(Boolean).join('\n');
    const body = `<main>\n  <article>\n    <h1>${escapeHtml(title)}</h1>\n    ${details}\n    ${content}  </article>\n</main>`;
    return Object.assign(page, { ...metadata, title, date, tags, template, layout, content, body, frontmatter: metadata });
  }
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>'"]/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[character] ?? character));
}
