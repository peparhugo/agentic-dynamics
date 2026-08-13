import type { PluginPage } from './types';

function escapeHtml(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

export function renderIndex(pages: PluginPage[]): string {
  const items = pages.map((page) => {
    const date = page.date
      ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>`
      : '';
    return `<li><a href="${escapeHtml(page.url)}">${escapeHtml(page.title)}</a>${date}</li>`;
  }).join('\n      ');

  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Pages</title>
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
