import { Page } from './types';

export function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

export function formatDate(date: Date): string {
  if (date.getTime() === 0) return '';
  return date.toISOString().slice(0, 10);
}

export function renderPage(page: Page, pages: Page[]): string {
  const tagsHtml = page.tags.length
    ? `<ul class="tags">${page.tags
        .map((tag) => `<li>${escapeHtml(tag)}</li>`)
        .join('')}</ul>`
    : '';
  const dateHtml = page.date.getTime()
    ? `<time datetime="${escapeHtml(page.date.toISOString())}">${formatDate(page.date)}</time>`
    : '';
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>${escapeHtml(page.title)}</title>
</head>
<body>
  <header>
    <nav><a href="index.html">Home</a></nav>
  </header>
  <main>
    <article>
      <h1>${escapeHtml(page.title)}</h1>
      ${dateHtml}
      ${tagsHtml}
      <div class="content">
${page.html}
      </div>
    </article>
  </main>
</body>
</html>
`;
}

export function renderIndex(pages: Page[]): string {
  const items = pages
    .map((page) => {
      const dateHtml = page.date.getTime()
        ? ` — <time datetime="${escapeHtml(page.date.toISOString())}">${formatDate(page.date)}</time>`
        : '';
      const tagsHtml = page.tags.length
        ? ` [${page.tags.map((tag) => escapeHtml(tag)).join(', ')}]`
        : '';
      return `<li><a href="${escapeHtml(page.slug)}.html">${escapeHtml(
        page.title
      )}</a>${dateHtml}${tagsHtml}</li>`;
    })
    .join('\n');
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Index</title>
</head>
<body>
  <header>
    <h1>Index</h1>
  </header>
  <main>
    <ul class="posts">
${items || '      <li>No posts</li>'}
    </ul>
  </main>
</body>
</html>
`;
}
