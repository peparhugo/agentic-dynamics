import { Page } from './types';

export function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function layout(title: string, body: string): string {
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>${escapeHtml(title)}</title>
</head>
<body>
${body}
</body>
</html>
`;
}

export function renderPage(page: Page): string {
  const tags = page.tags.length
    ? `<ul class="tags">${page.tags.map((tag) => `<li>${escapeHtml(tag)}</li>`).join('')}</ul>`
    : '';
  const date = page.date ? `<p class="date">${escapeHtml(page.date)}</p>` : '';
  const body = `<article>
<h1>${escapeHtml(page.title)}</h1>
${date}
${tags}
<div class="content">
${page.html}
</div>
<p><a href="index.html">&larr; Back to index</a></p>
</article>`;
  return layout(page.title, body);
}

export function renderIndex(pages: Page[]): string {
  const sorted = [...pages].sort((a, b) => (b.date || '').localeCompare(a.date || ''));
  const items = sorted
    .map((page) => {
      const date = page.date ? ` <span class="date">${escapeHtml(page.date)}</span>` : '';
      return `<li><a href="${escapeHtml(page.outputPath)}">${escapeHtml(page.title)}</a>${date}</li>`;
    })
    .join('\n');
  const body = `<h1>Site Index</h1>
<ul class="pages">
${items}
</ul>`;
  return layout('Site Index', body);
}
