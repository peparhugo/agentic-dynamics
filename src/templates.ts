import { Page } from './ssg';

export function escapeHtml(input: string): string {
  return input
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function pageMeta(page: Page): string {
  const parts: string[] = [];
  if (page.date) {
    parts.push(`<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>`);
  }
  if (page.tags.length > 0) {
    parts.push(
      `<span class="tags">${page.tags.map((t) => `<span class="tag">${escapeHtml(t)}</span>`).join('')}</span>`
    );
  }
  return parts.length > 0 ? `<p class="meta">${parts.join(' ')}</p>` : '';
}

function baseLayout(title: string, body: string): string {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${escapeHtml(title)}</title>
</head>
<body>
  <header>
    <a href="index.html">Home</a>
  </header>
  <main>
${body}
  </main>
</body>
</html>
`;
}

export function renderPage(page: Page): string {
  const body = `    <article>
      <h1>${escapeHtml(page.title)}</h1>
${pageMeta(page)}
${page.html}
    </article>
`;
  return baseLayout(page.title, body);
}

export function renderIndex(pages: Page[]): string {
  const listItems = pages
    .map((page) => {
      const meta = page.date ? ` <small>${escapeHtml(page.date)}</small>` : '';
      return `      <li><a href="${escapeHtml(page.slug)}.html">${escapeHtml(page.title)}</a>${meta}</li>`;
    })
    .join('\n');

  const body = `    <h1>All Posts</h1>
    <ul>
${listItems || '      <li>No posts found.</li>'}
    </ul>
`;
  return baseLayout('Home', body);
}
