import { Page } from './types';

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

export interface PageTemplateData {
  title: string;
  date?: string;
  tags: string[];
  body: string;
}

export function renderPageTemplate(data: PageTemplateData): string {
  const { title, date, tags, body } = data;
  const dateHtml = date ? `<p class="date">${escapeHtml(date)}</p>\n` : '';
  const tagsHtml = tags.length
    ? `<ul class="tags">${tags.map((tag) => `<li>${escapeHtml(tag)}</li>`).join('')}</ul>\n`
    : '';
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>${escapeHtml(title)}</title>
</head>
<body>
<article>
<h1>${escapeHtml(title)}</h1>
${dateHtml}${tagsHtml}${body}
</article>
</body>
</html>
`;
}

export function renderIndexTemplate(pages: Page[]): string {
  const items = pages
    .map((page) => {
      const dateHtml = page.date ? ` <span class="date">${escapeHtml(page.date)}</span>` : '';
      return `<li><a href="${page.outputPath}">${escapeHtml(page.title)}</a>${dateHtml}</li>`;
    })
    .join('\n');
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Index</title>
</head>
<body>
<h1>All Pages</h1>
<ul class="page-list">
${items}
</ul>
</body>
</html>
`;
}
