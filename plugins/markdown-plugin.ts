import * as fs from 'fs';
import { parseMarkdownFile } from '../src/frontmatter';
import { renderMarkdown } from '../src/markdown';
import { Page } from '../src/page';
import { Plugin } from '../src/plugin';
import { DEFAULT_LAYOUT_NAME, DEFAULT_TEMPLATE_NAME } from '../src/templates';

function titleFromSlug(slug: string): string {
  const base = slug.split('/').pop() || slug;
  return base
    .replace(/[-_]+/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

/**
 * Built-in plugin that turns a raw `.md` file into a fully populated Page:
 * splits frontmatter from body, renders the body to HTML, and resolves
 * title/date/tags/template/layout (falling back to sensible defaults).
 */
export function markdownPlugin(): Plugin {
  return {
    name: 'markdown',
    onFile(page: Page): Page {
      const raw = fs.readFileSync(page.sourcePath, 'utf-8');
      const { data, content } = parseMarkdownFile(raw);
      const html = renderMarkdown(content);

      const title = typeof data.title === 'string' && data.title.trim() ? data.title : titleFromSlug(page.slug);
      const date = typeof data.date === 'string' && data.date.trim() ? data.date : null;
      const tags = Array.isArray(data.tags) ? data.tags.map(String) : [];
      const template =
        typeof data.template === 'string' && data.template.trim() ? data.template : DEFAULT_TEMPLATE_NAME;
      const layout = typeof data.layout === 'string' && data.layout.trim() ? data.layout : DEFAULT_LAYOUT_NAME;

      return { ...page, title, date, tags, html, template, layout };
    },
  };
}
