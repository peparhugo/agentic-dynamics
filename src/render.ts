/**
 * HTML templates for individual pages and the site index.
 */

import type { Frontmatter, Page } from './types';

/** Escape HTML-sensitive characters in a string. */
export function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/** Build the `<title>` value for a page. */
export function pageTitle(data: Frontmatter, fallback: string): string {
  return typeof data.title === 'string' && data.title.trim() ? data.title : fallback;
}

/** Render a single page into a complete HTML document. */
export function renderPage(page: Page): string {
  const title = escapeHtml(page.title);

  const meta: string[] = [];
  if (page.date) {
    meta.push(`<p class="date">${escapeHtml(page.date)}</p>`);
  }
  if (page.tags.length > 0) {
    const tags = page.tags.map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`).join(' ');
    meta.push(`<p class="tags">${tags}</p>`);
  }

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${title}</title>
</head>
<body>
  <header>
    <h1>${title}</h1>
    ${meta.join('\n    ')}
  </header>
  <main>
${page.html}
  </main>
  <footer>
    <p><a href="index.html">&laquo; Back to index</a></p>
  </footer>
</body>
</html>
`;
}

/** Render the site index listing every page. */
export function renderIndex(pages: Page[]): string {
  const items = pages
    .map((page) => {
      const title = escapeHtml(page.title);
      const date = page.date ? ` <span class="date">${escapeHtml(page.date)}</span>` : '';
      const tags = page.tags.length
        ? ` <span class="tags">${page.tags.map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`).join(' ')}</span>`
        : '';
      return `    <li><a href="${escapeHtml(page.outputName)}">${title}</a>${date}${tags}</li>`;
    })
    .join('\n');

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Index</title>
</head>
<body>
  <header>
    <h1>Site Index</h1>
  </header>
  <main>
    <ul>
${items || '    <li>No pages yet.</li>'}
    </ul>
  </main>
</body>
</html>
`;
}
