import { escapeHtml } from './escape';
import type { Page } from './types';

/**
 * Built-in rendering used when no template engine is configured. Mirrors the
 * historical output of the generator so templated and non-templated sites
 * stay consistent.
 */
export function renderPage(page: Page): string {
  const date = page.date ? `<p class="date">${escapeHtml(page.date)}</p>` : '';
  const tags = page.tags
    ? `<ul class="tags">${page.tags
        .map((tag) => `<li>${escapeHtml(tag)}</li>`)
        .join('')}</ul>`
    : '';
  return [
    '<!DOCTYPE html>',
    '<html lang="en">',
    '<head>',
    '<meta charset="utf-8">',
    '<meta name="viewport" content="width=device-width, initial-scale=1">',
    `<title>${escapeHtml(page.title)}</title>`,
    '</head>',
    '<body>',
    '<header>',
    `<h1>${escapeHtml(page.title)}</h1>`,
    date,
    tags,
    '</header>',
    '<main>',
    page.contentHtml,
    '</main>',
    '</body>',
    '</html>',
    '',
  ].join('\n');
}

export function sortPages(pages: Page[]): Page[] {
  return [...pages].sort((a, b) => {
    if (a.date && b.date) {
      return b.date.localeCompare(a.date);
    }
    if (a.date) return -1;
    if (b.date) return 1;
    return a.slug.localeCompare(b.slug);
  });
}

export function renderIndex(pages: Page[]): string {
  const items = sortPages(pages)
    .map((page) => {
      const date = page.date ? ` <span class="date">${escapeHtml(page.date)}</span>` : '';
      return `    <li><a href="${escapeHtml(page.slug)}.html">${escapeHtml(
        page.title
      )}</a>${date}</li>`;
    })
    .join('\n');
  return [
    '<!DOCTYPE html>',
    '<html lang="en">',
    '<head>',
    '<meta charset="utf-8">',
    '<meta name="viewport" content="width=device-width, initial-scale=1">',
    '<title>Index</title>',
    '</head>',
    '<body>',
    '<h1>Index</h1>',
    '<ul>',
    items,
    '</ul>',
    '</body>',
    '</html>',
    '',
  ].join('\n');
}
