import fs from 'fs';
import path from 'path';
import matter from 'gray-matter';
import { marked } from 'marked';
import { TemplateEngine } from './templates';

interface Page {
  title: string;
  date: string;
  tags: string[];
  content: string;
  slug: string;
  layout?: string;
  template?: string;
}

export function parseMarkdownFile(filePath: string): Page | null {
  const raw = fs.readFileSync(filePath, 'utf-8');
  const { data, content } = matter(raw);
  const slug = path.basename(filePath, '.md');

  const parsed = marked.parse(content);
  const html = typeof parsed === 'object' && parsed !== null && 'html' in parsed
    ? (parsed as { html: string }).html
    : parsed as string;

  const date = data.date instanceof Date
    ? data.date.toISOString().split('T')[0]
    : data.date || '';

  return {
    title: data.title || slug,
    date,
    tags: data.tags || [],
    content: html,
    slug,
    layout: data.layout || undefined,
    template: data.template || undefined,
  };
}

export function readContentDirectory(contentDir: string): Page[] {
  if (!fs.existsSync(contentDir)) {
    return [];
  }

  const entries = fs.readdirSync(contentDir);
  const pages: Page[] = [];

  for (const entry of entries) {
    if (entry.endsWith('.md')) {
      const page = parseMarkdownFile(path.join(contentDir, entry));
      if (page) {
        pages.push(page);
      }
    }
  }

  return pages;
}

function renderPage(page: Page): string {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${page.title}</title>
${page.tags.length ? `  <meta name="keywords" content="${page.tags.join(', ')}">` : ''}
</head>
<body>
  <header>
    <nav><a href="index.html">Home</a></nav>
  </header>
  <main>
    <article>
      <h1>${page.title}</h1>
${page.date ? `      <time>${page.date}</time>` : ''}
      <div>${page.content}</div>
    </article>
  </main>
</body>
</html>`;
}

function renderIndex(pages: Page[]): string {
  const listItems = pages
    .map((page) => {
      const dateStr = page.date ? ` <time>${page.date}</time>` : '';
      const tagsStr = page.tags.length ? ` [${page.tags.join(', ')}]` : '';
      return `      <li><a href="${page.slug}.html">${page.title}</a>${dateStr}${tagsStr}</li>`;
    })
    .join('\n');

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>All Pages</title>
</head>
<body>
  <header>
    <h1>All Pages</h1>
  </header>
  <main>
    <ul>
${listItems}
    </ul>
  </main>
</body>
</html>`;
}

export function generateSite(contentDir: string, outputDir: string, templatesDir?: string): number {
  const pages = readContentDirectory(contentDir);

  if (pages.length === 0) {
    console.log(`No markdown files found in ${contentDir}`);
    return 0;
  }

  fs.mkdirSync(outputDir, { recursive: true });

  const engine = templatesDir ? new TemplateEngine(templatesDir) : null;
  const useTemplates = engine && engine.initialized;

  for (const page of pages) {
    const html = useTemplates
      ? (engine!.render(page) || renderPage(page))
      : renderPage(page);
    fs.writeFileSync(path.join(outputDir, `${page.slug}.html`), html);
  }

  const indexHtml = useTemplates
    ? (engine!.renderIndex(pages) || renderIndex(pages))
    : renderIndex(pages);
  fs.writeFileSync(path.join(outputDir, 'index.html'), indexHtml);

  console.log(`Generated ${pages.length + 1} files in ${outputDir}`);
  return pages.length + 1;
}
