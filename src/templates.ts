import { Page } from './page';
import { escapeHtml, tagSpans, dateElement } from './html';

export function pageHtml(page: Page): string {
  const tags = tagSpans(page.tags);
  const date = dateElement(page.date);
  const metaLine = [date, tags].filter((part) => part.length > 0).join(' ');
  return [
    '<!DOCTYPE html>',
    '<html lang="en">',
    '<head>',
    '  <meta charset="utf-8">',
    `  <meta name="viewport" content="width=device-width, initial-scale=1">`,
    `  <title>${escapeHtml(page.title)}</title>`,
    '</head>',
    '<body>',
    '  <header>',
    `    <h1>${escapeHtml(page.title)}</h1>`,
    metaLine ? `    <p class="meta">${metaLine}</p>` : '',
    '    <p><a href="index.html">&larr; Home</a></p>',
    '  </header>',
    '  <main>',
    page.contentHtml,
    '  </main>',
    '</body>',
    '</html>',
    '',
  ]
    .filter((line) => line !== undefined)
    .join('\n');
}

export function indexHtml(pages: Page[]): string {
  const items = pages
    .map((page) => {
      const date = dateElement(page.date);
      const tags = tagSpans(page.tags);
      const meta = [date, tags].filter((part) => part.length > 0).join(' ');
      return [
        '    <li>',
        `      <a href="${escapeHtml(page.slug)}.html">${escapeHtml(page.title)}</a>`,
        meta ? `      <span class="meta">${meta}</span>` : '',
        '    </li>',
      ]
        .filter((line) => line !== '')
        .join('\n');
    })
    .join('\n');

  return [
    '<!DOCTYPE html>',
    '<html lang="en">',
    '<head>',
    '  <meta charset="utf-8">',
    '  <meta name="viewport" content="width=device-width, initial-scale=1">',
    '  <title>Home</title>',
    '</head>',
    '<body>',
    '  <header>',
    '    <h1>Home</h1>',
    '  </header>',
    '  <main>',
    pages.length > 0 ? '    <ul class="pages">\n' + items + '\n    </ul>' : '    <p>No pages yet.</p>',
    '  </main>',
    '</body>',
    '</html>',
    '',
  ].join('\n');
}
