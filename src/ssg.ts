import fs from 'fs';
import path from 'path';
import matter from 'gray-matter';
import { marked } from 'marked';
import { Page, SSGOptions } from './types';

function slugify(filename: string): string {
  const name = path.basename(filename, path.extname(filename));
  return name.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '');
}

function readMarkdownFiles(contentDir: string): string[] {
  if (!fs.existsSync(contentDir)) {
    return [];
  }
  return fs.readdirSync(contentDir)
    .filter(f => f.endsWith('.md'))
    .map(f => path.join(contentDir, f));
}

function parsePage(filePath: string): Page {
  const raw = fs.readFileSync(filePath, 'utf-8');
  const { data, content } = matter(raw);
  const html = marked.parse(content) as string;
  const slug = slugify(path.basename(filePath));
  return {
    frontmatter: {
      title: data.title || slug,
      date: data.date,
      tags: data.tags,
    },
    html,
    slug,
  };
}

function buildPageHTML(page: Page): string {
  const { title, date, tags } = page.frontmatter;
  const tagsHtml = tags && tags.length > 0
    ? `<div class="tags">Tags: ${tags.join(', ')}</div>`
    : '';
  const dateHtml = date
    ? `<div class="date">${new Date(date).toLocaleDateString()}</div>`
    : '';

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${title}</title>
</head>
<body>
  <main>
    <article>
      <h1>${title}</h1>
      ${dateHtml}
      ${tagsHtml}
      ${page.html}
    </article>
  </main>
  <footer>
    <a href="index.html">Back to index</a>
  </footer>
</body>
</html>`;
}

function buildIndexHTML(pages: Page[]): string {
  const listItems = pages
    .map(page => {
      const { title, date, tags } = page.frontmatter;
      const dateStr = date ? ` — ${new Date(date).toLocaleDateString()}` : '';
      const tagsStr = tags && tags.length > 0 ? ` [${tags.join(', ')}]` : '';
      return `<li><a href="${page.slug}.html">${title}</a>${dateStr}${tagsStr}</li>`;
    })
    .join('\n      ');

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>My Static Site</title>
</head>
<body>
  <main>
    <h1>Pages</h1>
    <ul>
      ${listItems}
    </ul>
  </main>
</body>
</html>`;
}

export function build(options: SSGOptions): void {
  const { contentDir, outputDir } = options;

  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  const files = readMarkdownFiles(contentDir);
  const pages: Page[] = [];

  for (const file of files) {
    const page = parsePage(file);
    pages.push(page);

    const pageHTML = buildPageHTML(page);
    const outPath = path.join(outputDir, `${page.slug}.html`);
    fs.writeFileSync(outPath, pageHTML, 'utf-8');
  }

  const indexHTML = buildIndexHTML(pages);
  fs.writeFileSync(path.join(outputDir, 'index.html'), indexHTML, 'utf-8');
}
