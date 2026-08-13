import { Page } from './types';

export function escapeHtml(input: string): string {
  return input
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

export function renderPage(page: Page): string {
  const tagsHtml = page.tags.length
    ? `<ul class="tags">${page.tags.map((t) => `<li>${escapeHtml(t)}</li>`).join('')}</ul>`
    : '';
  const dateHtml = page.date ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '';

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
<h1>${escapeHtml(page.title)}</h1>
${dateHtml}
${tagsHtml}
${page.html}
</article>
</body>
</html>
`;
}

export function renderIndex(pages: Page[]): string {
  const sorted = [...pages].sort((a, b) => (b.date || '').localeCompare(a.date || ''));
  const items = sorted
    .map((page) => {
      const dateHtml = page.date ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '';
      return `<li><a href="${escapeHtml(page.outputFile)}">${escapeHtml(page.title)}</a>${dateHtml}</li>`;
    })
    .join('\n');

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
<ul class="page-list">
${items}
</ul>
</body>
</html>
`;
}
