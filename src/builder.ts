import fs from 'fs';
import path from 'path';
import { Page } from './types';
import { parseMarkdown, slugify } from './markdown';

const MARKDOWN_RE = /\.(md|markdown)$/i;

export function collectMarkdownFiles(contentDir: string): string[] {
  if (!fs.existsSync(contentDir)) {
    return [];
  }
  const results: string[] = [];
  const walk = (dir: string): void => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(full);
      } else if (entry.isFile() && MARKDOWN_RE.test(entry.name)) {
        results.push(full);
      }
    }
  };
  walk(contentDir);
  return results.sort();
}

export function readPages(contentDir: string): Page[] {
  return collectMarkdownFiles(contentDir).map((filePath) => {
    const slug = slugify(path.basename(filePath));
    const raw = fs.readFileSync(filePath, 'utf8');
    const doc = parseMarkdown(slug, raw);
    return {
      slug: doc.slug,
      title: doc.title,
      date: doc.date,
      tags: doc.tags,
      content: doc.content,
    };
  });
}

export function sortPages(pages: Page[]): Page[] {
  return [...pages].sort((a, b) => {
    const da = a.date ? Date.parse(a.date) : -Infinity;
    const db = b.date ? Date.parse(b.date) : -Infinity;
    if (da !== db) {
      return db - da;
    }
    return a.title.localeCompare(b.title);
  });
}

export function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

export function renderPage(page: Page): string {
  const dateTag = page.date
    ? `    <p class="date"><time datetime="${escapeHtml(page.date)}">${escapeHtml(
        page.date,
      )}</time></p>\n`
    : '';
  const tags = page.tags.length
    ? `    <p class="tags">${page.tags
        .map((t) => `<span class="tag">${escapeHtml(t)}</span>`)
        .join(' ')}</p>\n`
    : '';
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${escapeHtml(page.title)}</title>
</head>
<body>
  <article>
    <h1>${escapeHtml(page.title)}</h1>
${dateTag}${tags}    ${page.content}
  </article>
  <p><a href="index.html">&larr; Back to index</a></p>
</body>
</html>
`;
}

export function renderIndex(pages: Page[]): string {
  const items = pages
    .map((p) => {
      const date = p.date ? ` <time>${escapeHtml(p.date)}</time>` : '';
      const tags = p.tags.length
        ? ` <span class="tags">${p.tags
            .map((t) => `#${escapeHtml(t)}`)
            .join(' ')}</span>`
        : '';
      return `    <li><a href="${encodeURIComponent(p.slug)}.html">${escapeHtml(
        p.title,
      )}</a>${date}${tags}</li>`;
    })
    .join('\n');

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Index</title>
</head>
<body>
  <h1>Pages</h1>
  <ul>
${items}
  </ul>
</body>
</html>
`;
}

export function buildSite(contentDir: string, outputDir: string): Page[] {
  const pages = sortPages(readPages(contentDir));
  fs.mkdirSync(outputDir, { recursive: true });
  fs.writeFileSync(path.join(outputDir, 'index.html'), renderIndex(pages), 'utf8');
  for (const page of pages) {
    fs.writeFileSync(
      path.join(outputDir, `${page.slug}.html`),
      renderPage(page),
      'utf8',
    );
  }
  return pages;
}
