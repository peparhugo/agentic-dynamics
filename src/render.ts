import * as path from 'path';
import { Page } from './plugin';
import { RenderContext } from './templates';

export function escapeHtml(input: string): string {
  return input
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

export function relativeIndexLink(outputPath: string): string {
  const dir = path.dirname(outputPath);
  const rel = path.relative(dir, 'index.html');
  return rel.split(path.sep).join('/');
}

export function renderMeta(date: string | null, tags: string[]): string {
  const meta: string[] = [];
  if (date) {
    meta.push(
      `<time datetime="${escapeHtml(date)}">${escapeHtml(date)}</time>`
    );
  }
  if (tags.length > 0) {
    meta.push(
      `<ul class="tags">${tags
        .map((tag) => `<li>${escapeHtml(tag)}</li>`)
        .join('')}</ul>`
    );
  }
  return meta.join('\n');
}

export function pageContext(page: Page): RenderContext {
  return {
    ...page.frontmatter,
    title: page.title,
    date: page.date,
    tags: page.tags,
    content: page.html,
    slug: page.slug,
    sourcePath: page.sourcePath,
    outputPath: page.outputPath,
    home: relativeIndexLink(page.outputPath),
    meta: renderMeta(page.date, page.tags),
  };
}

export function renderIndex(pages: Page[]): string {
  const items = pages
    .map((page) => {
      const date = page.date
        ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(
            page.date
          )}</time>`
        : '';
      const tags = page.tags.length
        ? ` <span class="tags">${page.tags
            .map((tag) => escapeHtml(tag))
            .join(', ')}</span>`
        : '';
      return `<li><a href="${escapeHtml(page.outputPath)}">${escapeHtml(
        page.title
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
<h1>Index</h1>
<ul>
${items}
</ul>
</body>
</html>
`;
}
