import { marked } from 'marked';
import type { Page } from './types';

export function renderMarkdown(markdown: string): string {
  return marked.parse(markdown, { async: false }) as string;
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function renderTags(tags: string[]): string {
  if (tags.length === 0) return '';
  const items = tags.map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`).join(' ');
  return `<div class="tags">${items}</div>`;
}

/**
 * Builds the inner listing markup for the generated index page. This is
 * injected into the `index` (or `default`) layout's `{{{body}}}` placeholder
 * by the template engine, so it is plain HTML rather than a full document.
 */
export function renderIndexBodyHtml(pages: Page[]): string {
  const items = pages
    .map((page) => {
      const dateHtml = page.date ? ` <span class="date">${escapeHtml(page.date)}</span>` : '';
      return `    <li>
      <a href="${escapeHtml(page.outputFile)}">${escapeHtml(page.title)}</a>${dateHtml}
      ${renderTags(page.tags)}
    </li>`;
    })
    .join('\n');

  return `<ul>
${items}
  </ul>`;
}
