import type { Page } from './types';

export function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

export function pagePath(page: Page): string {
  return `${page.slug}.html`;
}

export function renderDocument(page: Page, content: string): string {
  const dateHtml = page.date
    ? `<p class="date"><time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time></p>`
    : '';
  const tagsHtml =
    page.tags.length > 0
      ? `<p class="tags">${page.tags
          .map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`)
          .join(' ')}</p>`
      : '';
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${escapeHtml(page.title)}</title>
</head>
<body>
  <header>
    <nav><a href="index.html">Home</a></nav>
    <h1>${escapeHtml(page.title)}</h1>
    ${dateHtml}
  </header>
  <main>
${content}
${tagsHtml}
  </main>
</body>
</html>
`;
}

export function renderPage(page: Page): string {
  return renderDocument(page, page.html);
}

export function renderIndexItems(pages: Page[]): string {
  return [...pages]
    .sort((a, b) => (b.date ?? '').localeCompare(a.date ?? ''))
    .map((page) => {
      const date = page.date
        ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>`
        : '';
      const tags =
        page.tags.length > 0
          ? ` <span class="tags">${page.tags.map((tag) => escapeHtml(tag)).join(', ')}</span>`
          : '';
      return `    <li><a href="${pagePath(page)}">${escapeHtml(page.title)}</a>${date}${tags}</li>`;
    })
    .join('\n');
}

export function renderIndexBody(pages: Page[]): string {
  return `    <ul>\n${renderIndexItems(pages)}\n    </ul>`;
}

export function renderIndex(pages: Page[]): string {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Index</title>
</head>
<body>
  <header>
    <h1>Index</h1>
  </header>
  <main>
${renderIndexBody(pages)}
  </main>
</body>
</html>
`;
}
