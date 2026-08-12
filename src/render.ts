import { Page } from './types';

function esc(value: string): string {
  return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function pageTitle(page: Page): string {
  return page.data.title || page.slug;
}

function tagsHtml(tags: string[] | undefined): string {
  if (!tags || tags.length === 0) return '';
  const items = tags.map((t) => `<span class="tag">${esc(t)}</span>`).join('');
  return `<div class="tags">${items}</div>`;
}

export function renderPage(page: Page): string {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>${esc(pageTitle(page))}</title>
</head>
<body>
  <header>
    <nav><a href="index.html">Home</a></nav>
  </header>
  <main>
    <h1>${esc(pageTitle(page))}</h1>
    ${page.data.date ? `<time datetime="${esc(page.data.date)}">${esc(page.data.date)}</time>` : ''}
    ${tagsHtml(page.data.tags)}
    <article>
${page.html}
    </article>
  </main>
</body>
</html>
`;
}

export function renderIndex(pages: Page[]): string {
  const sorted = [...pages].sort((a, b) => {
    const da = a.data.date || '';
    const db = b.data.date || '';
    if (da !== db) return da < db ? 1 : -1;
    return a.slug.localeCompare(b.slug);
  });

  const items = sorted
    .map(
      (p) => `    <li>
      <a href="${p.slug}.html">${esc(pageTitle(p))}</a>
      ${p.data.date ? `<time datetime="${esc(p.data.date)}">${esc(p.data.date)}</time>` : ''}
    </li>`
    )
    .join('\n');

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Home</title>
</head>
<body>
  <main>
    <h1>Pages</h1>
    <ul>
${items}
    </ul>
  </main>
</body>
</html>
`;
}
