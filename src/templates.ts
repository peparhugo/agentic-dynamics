import { Page } from './types';

export function escapeHtml(input: string): string {
  return input
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/**
 * Renders a page's inner content (heading, date, tags, body HTML) without
 * the surrounding document shell. Used both by the built-in `renderPage`
 * and as the `{{{body}}}` value fed into custom Handlebars layouts.
 */
export function renderArticleBody(page: Page): string {
  const tagsHtml = page.tags.length
    ? `<ul class="tags">${page.tags.map((t) => `<li>${escapeHtml(t)}</li>`).join('')}</ul>`
    : '';
  const dateHtml = page.date ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '';

  return `<h1>${escapeHtml(page.title)}</h1>
${dateHtml}
${tagsHtml}
${page.html}`;
}

export function renderPage(page: Page): string {
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>${escapeHtml(page.title)}</title>
<link rel="stylesheet" href="style.css">
</head>
<body>
<header>
<a href="index.html">&larr; Home</a>
</header>
<article>
${renderArticleBody(page)}
</article>
</body>
</html>
`;
}

/**
 * Renders the home page's page-listing markup, without the surrounding
 * document shell. Used both by the built-in `renderIndex` and as the
 * `{{{body}}}` value fed into a custom "index" Handlebars layout.
 */
export function renderIndexBody(pages: Page[]): string {
  const sorted = [...pages].sort((a, b) => (b.date || '').localeCompare(a.date || ''));
  const items = sorted
    .map((page) => {
      const dateHtml = page.date ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '';
      return `<li><a href="${escapeHtml(page.outputFile)}">${escapeHtml(page.title)}</a>${dateHtml}</li>`;
    })
    .join('\n');

  return `<ul class="page-list">
${items}
</ul>`;
}

export function renderIndex(pages: Page[]): string {
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Home</title>
<link rel="stylesheet" href="style.css">
</head>
<body>
<header>
<h1>Home</h1>
</header>
${renderIndexBody(pages)}
</body>
</html>
`;
}
