import { Page } from './types';

export function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function renderMeta(page: Page): string {
  const parts: string[] = [];
  if (page.frontmatter.date) {
    parts.push(`<time datetime="${escapeHtml(page.frontmatter.date)}">${escapeHtml(page.frontmatter.date)}</time>`);
  }
  if (page.frontmatter.tags.length > 0) {
    const tags = page.frontmatter.tags.map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`).join(' ');
    parts.push(`<span class="tags">${tags}</span>`);
  }
  return parts.length > 0 ? `<p class="meta">${parts.join(' &middot; ')}</p>` : '';
}

export function renderPageHtml(page: Page): string {
  const title = escapeHtml(page.frontmatter.title);
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${title}</title>
  <link rel="stylesheet" href="${'../'.repeat(page.slug.split('/').length - 1)}style.css">
</head>
<body>
  <header>
    <a href="${'../'.repeat(page.slug.split('/').length - 1)}index.html">&larr; Back to index</a>
  </header>
  <main>
    <article>
      <h1>${title}</h1>
      ${renderMeta(page)}
      ${page.contentHtml}
    </article>
  </main>
</body>
</html>
`;
}

export function renderIndexHtml(pages: Page[], siteTitle: string): string {
  const items = pages
    .map((page) => {
      const title = escapeHtml(page.frontmatter.title);
      const href = `${page.slug}.html`;
      return `      <li>
        <a href="${escapeHtml(href)}">${title}</a>
        ${renderMeta(page)}
      </li>`;
    })
    .join('\n');

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${escapeHtml(siteTitle)}</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <header>
    <h1>${escapeHtml(siteTitle)}</h1>
  </header>
  <main>
    <ul class="page-list">
${items}
    </ul>
  </main>
</body>
</html>
`;
}

export const DEFAULT_STYLESHEET = `body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; max-width: 40rem; margin: 2rem auto; padding: 0 1rem; line-height: 1.6; color: #1a1a1a; }
a { color: #0b5fff; }
.page-list { list-style: none; padding: 0; }
.page-list li { margin-bottom: 1.25rem; }
.meta { color: #666; font-size: 0.875rem; margin: 0.25rem 0; }
.tag { background: #eee; border-radius: 0.25rem; padding: 0.1rem 0.4rem; font-size: 0.75rem; }
`;
