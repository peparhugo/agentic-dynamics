import { Page } from './types';
import { escapeHtml } from './parser';

function tagsHtml(tags: string[]): string {
  if (tags.length === 0) return '';
  const chips = tags.map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`).join('');
  return `<div class="tags">${chips}</div>`;
}

export function renderPage(page: Page): string {
  const title = escapeHtml(page.title);
  const date = page.date ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '';
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${title}</title>
</head>
<body>
  <header>
    <nav><a href="index.html">Home</a></nav>
  </header>
  <main>
    <article>
      <h1>${title}</h1>
      ${date ? `<p class="date">${date}</p>` : ''}
      ${tagsHtml(page.tags)}
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
  const sorted = [...pages].sort((a, b) => {
    if (a.date && b.date) {
      return a.date < b.date ? 1 : a.date > b.date ? -1 : 0;
    }
    return a.title.localeCompare(b.title);
  });

  const items = sorted
    .map((page) => {
      const date = page.date ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time> ` : '';
      return `    <li>
      <a href="${escapeHtml(page.slug)}.html"><h2>${escapeHtml(page.title)}</h2></a>
      ${date ? `<span class="date">${date}</span>` : ''}
      ${tagsHtml(page.tags)}
    </li>`;
    })
    .join('\n');

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Home</title>
</head>
<body>
  <header><h1>Site</h1></header>
  <main>
    <ul class="pages">
${items}
    </ul>
  </main>
</body>
</html>
`;
}
