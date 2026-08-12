import { promises as fs } from 'fs';
import { join, relative, basename } from 'path';
import { parsePage, pageFileName } from './markdown';
import type { Page, BuildOptions } from './types';

function escapeHtml(input: string): string {
  return input
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function renderTags(tags: string[]): string {
  if (tags.length === 0) return '';
  const chips = tags.map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`).join('');
  return `<div class="tags">${chips}</div>`;
}

function renderPageBody(page: Page): string {
  const dateLine = page.date ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '';
  return `
<article class="page">
  <h1 class="page-title">${escapeHtml(page.title)}</h1>
  ${dateLine}
  ${renderTags(page.tags)}
  <div class="page-content">${page.contentHtml}</div>
  <p><a href="index.html">&larr; Back to index</a></p>
</article>`;
}

function layoutShell(body: string, title: string): string {
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
</html>
`;
}

export function renderPage(page: Page): string {
  return layoutShell(renderPageBody(page), page.title);
}

export function renderIndex(pages: Page[]): string {
  const sorted = [...pages].sort((a, b) => {
    if (a.date && b.date) return b.date.localeCompare(a.date);
    return a.title.localeCompare(b.title);
  });

  const items = sorted
    .map((page) => {
      const href = pageFileName(page.fileName);
      return `<li>
  <a href="${escapeHtml(href)}">${escapeHtml(page.title)}</a>
  ${page.date ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : ''}
  ${renderTags(page.tags)}
</li>`;
    })
    .join('\n');

  const payload = escapeHtml(JSON.stringify(sorted.map((p) => ({
    title: p.title,
    date: p.date,
    tags: p.tags,
    href: pageFileName(p.fileName)
  }))));

  const body = `
<header class="site-header">
  <h1>Pages</h1>
</header>
<ul class="page-list" id="page-list">${items}</ul>
<div id="app" hidden></div>
<script id="ssg-data" type="application/json">${payload}</script>
<script>
  (function () {
    var data = JSON.parse(document.getElementById('ssg-data').textContent);
    var list = document.getElementById('page-list');
    if (data.length === 0) {
      list.innerHTML = '<li>No pages found.</li>';
    }
    var app = document.getElementById('app');
    var links = list.querySelectorAll('a');
    for (var i = 0; i < links.length; i++) {
      (function (link) {
        link.addEventListener('click', function (e) {
          e.preventDefault();
          var target = link.getAttribute('href');
          var page = null;
          for (var j = 0; j < data.length; j++) {
            if (data[j].href === target) { page = data[j]; break; }
          }
          if (page) {
            app.innerHTML = '<h1>' + page.title + '</h1>' +
              (page.date ? '<time>' + page.date + '</time>' : '') +
              '<p><a href="index.html">&larr; Back to index</a></p>';
            app.hidden = false;
            list.hidden = true;
          }
        });
      })(links[i]);
    }
  })();
</script>
`;
  return layoutShell(body, 'Pages');
}

export async function collectPages(contentDir: string): Promise<Page[]> {
  const entries = await fs.readdir(contentDir, { withFileTypes: true });
  const pages: Page[] = [];
  for (const entry of entries) {
    if (!entry.isFile() || !/\.md$/i.test(entry.name)) continue;
    const fullPath = join(contentDir, entry.name);
    const contents = await fs.readFile(fullPath, 'utf8');
    pages.push(parsePage(entry.name, contents));
  }
  return pages;
}

export async function buildSite(options: BuildOptions): Promise<Page[]> {
  const contentDir = options.contentDir;
  const outputDir = options.outputDir;

  await fs.mkdir(outputDir, { recursive: true });

  const pages = await collectPages(contentDir);

  const indexHtml = renderIndex(pages);
  await fs.writeFile(join(outputDir, 'index.html'), indexHtml, 'utf8');

  for (const page of pages) {
    const html = renderPage(page);
    await fs.writeFile(join(outputDir, pageFileName(page.fileName)), html, 'utf8');
  }

  return pages;
}
