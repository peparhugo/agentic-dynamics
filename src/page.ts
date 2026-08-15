export interface Page {
  slug: string;
  title: string;
  date: string | null;
  tags: string[];
  html: string;
  sourcePath: string;
  outputPath: string;
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

export function renderPageHtml(page: Page): string {
  const tagsHtml = page.tags.length
    ? `<ul class="tags">${page.tags.map((tag) => `<li>${escapeHtml(tag)}</li>`).join('')}</ul>`
    : '';
  const dateHtml = page.date ? `<p class="date">${escapeHtml(page.date)}</p>` : '';

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>${escapeHtml(page.title)}</title>
</head>
<body>
<a href="index.html">&larr; Back to index</a>
<h1>${escapeHtml(page.title)}</h1>
${dateHtml}
${tagsHtml}
<article>
${page.html}
</article>
</body>
</html>
`;
}

export function renderIndexHtml(pages: Page[]): string {
  const items = pages
    .map((page) => {
      const dateHtml = page.date ? ` <span class="date">${escapeHtml(page.date)}</span>` : '';
      return `<li><a href="${escapeHtml(page.outputPath)}">${escapeHtml(page.title)}</a>${dateHtml}</li>`;
    })
    .join('\n');

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Index</title>
</head>
<body>
<h1>Index</h1>
<ul class="pages">
${items}
</ul>
</body>
</html>
`;
}
