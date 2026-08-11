import fs from 'fs';
import path from 'path';
import { PageData, ParseResult } from './types';

function wrapPage(title: string, body: string): string {
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
</html>`;
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function renderIndex(pages: PageData[]): string {
  const sorted = [...pages].sort((a, b) =>
    b.frontmatter.date.localeCompare(a.frontmatter.date)
  );

  const items = sorted
    .map(
      (page) => `
    <article>
      <h2><a href="${escapeHtml(page.slug)}.html">${escapeHtml(page.frontmatter.title)}</a></h2>
      ${page.frontmatter.date ? `<time>${escapeHtml(page.frontmatter.date)}</time>` : ''}
      ${page.frontmatter.tags.length ? `<p>Tags: ${escapeHtml(page.frontmatter.tags.join(', '))}</p>` : ''}
    </article>`
    )
    .join('\n');

  const body = `
  <header>
    <h1>Blog</h1>
  </header>
  <main>
    ${items || '<p>No posts yet.</p>'}
  </main>`;

  return wrapPage('Blog', body);
}

function renderPage(page: PageData): string {
  const body = `
  <header>
    <h1>${escapeHtml(page.frontmatter.title)}</h1>
    ${page.frontmatter.date ? `<time>${escapeHtml(page.frontmatter.date)}</time>` : ''}
    ${page.frontmatter.tags.length ? `<p>Tags: ${escapeHtml(page.frontmatter.tags.join(', '))}</p>` : ''}
  </header>
  <main>
    ${page.html}
  </main>
  <footer>
    <a href="index.html">&larr; Back to index</a>
  </footer>`;

  return wrapPage(page.frontmatter.title, body);
}

export function generateSite(
  { pages }: ParseResult,
  outputDir: string
): void {
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  for (const page of pages) {
    const html = renderPage(page);
    fs.writeFileSync(path.join(outputDir, `${page.slug}.html`), html);
  }

  const indexHtml = renderIndex(pages);
  fs.writeFileSync(path.join(outputDir, 'index.html'), indexHtml);
}
