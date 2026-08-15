import { Page } from './types';

export function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function formatDate(date: string | undefined): string {
  if (!date) {
    return '';
  }
  const d = new Date(date);
  if (Number.isNaN(d.getTime())) {
    return date;
  }
  return d.toISOString().slice(0, 10);
}

export function renderPageHtml(page: Page): string {
  const title = escapeHtml(page.title);
  const date = formatDate(page.date);
  const dateLine = date ? `<p class="page-date">${escapeHtml(date)}</p>` : '';
  const tags = page.tags
    .map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`)
    .join(' ');
  const tagsLine = tags ? `<p class="page-tags">${tags}</p>` : '';

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${title}</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 48rem; margin: 2rem auto; padding: 0 1rem; line-height: 1.6; }
    a { color: #1a73e8; }
    .tag { background: #eef1f5; border-radius: 4px; padding: 0.1rem 0.5rem; margin-right: 0.25rem; }
  </style>
</head>
<body>
  <nav><a href="index.html">&larr; Home</a></nav>
  <article>
    <h1>${title}</h1>
    ${dateLine}
    ${tagsLine}
    <div class="content">
${page.html}
    </div>
  </article>
</body>
</html>
`;
}

export function renderIndexHtml(pages: Page[]): string {
  const sorted = [...pages].sort((a, b) => {
    const ad = a.date ? new Date(a.date).getTime() : 0;
    const bd = b.date ? new Date(b.date).getTime() : 0;
    return bd - ad;
  });

  const items = sorted
    .map((page) => {
      const date = formatDate(page.date);
      const datePart = date ? `<span class="date">${escapeHtml(date)}</span> ` : '';
      const tags = page.tags
        .map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`)
        .join(' ');
      const tagsPart = tags ? ` ${tags}` : '';
      return `<li>${datePart}<a href="${escapeHtml(page.slug)}.html">${escapeHtml(page.title)}</a>${tagsPart}</li>`;
    })
    .join('\n    ');

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Index</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 48rem; margin: 2rem auto; padding: 0 1rem; line-height: 1.6; }
    a { color: #1a73e8; }
    .tag { background: #eef1f5; border-radius: 4px; padding: 0.1rem 0.5rem; margin-right: 0.25rem; }
    .date { color: #666; }
  </style>
</head>
<body>
  <h1>Index</h1>
  <ul>
    ${items}
  </ul>
</body>
</html>
`;
}
