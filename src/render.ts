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

export function renderPageHtml(page: Page): string {
  const dateHtml = page.date ? `<p class="date">${escapeHtml(page.date)}</p>` : '';
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${escapeHtml(page.title)}</title>
</head>
<body>
  <nav><a href="index.html">&larr; Back to index</a></nav>
  <article>
    <h1>${escapeHtml(page.title)}</h1>
    ${dateHtml}
    ${renderTags(page.tags)}
    ${page.html}
  </article>
</body>
</html>
`;
}

export function renderIndexHtml(pages: Page[]): string {
  const items = pages
    .map((page) => {
      const dateHtml = page.date ? ` <span class="date">${escapeHtml(page.date)}</span>` : '';
      return `    <li>
      <a href="${escapeHtml(page.outputFile)}">${escapeHtml(page.title)}</a>${dateHtml}
      ${renderTags(page.tags)}
    </li>`;
    })
    .join('\n');

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Home</title>
</head>
<body>
  <h1>All Pages</h1>
  <ul>
${items}
  </ul>
</body>
</html>
`;
}
