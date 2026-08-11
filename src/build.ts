import fs from 'fs';
import path from 'path';
import matter from 'gray-matter';
import { marked } from 'marked';
import { Page, BuildOptions } from './types';

function readPages(contentDir: string): Page[] {
  const absDir = path.resolve(contentDir);
  if (!fs.existsSync(absDir)) {
    throw new Error(`Content directory not found: ${absDir}`);
  }

  const entries = fs.readdirSync(absDir, { withFileTypes: true });
  const pages: Page[] = [];

  for (const entry of entries) {
    if (!entry.isFile() || !entry.name.endsWith('.md')) {
      continue;
    }

    const filePath = path.join(absDir, entry.name);
    const raw = fs.readFileSync(filePath, 'utf-8');
    const parsed = matter(raw);

    const slug = entry.name.replace(/\.md$/, '');
    const rawData = parsed.data as Record<string, unknown>;

    if (!rawData.title || typeof rawData.title !== 'string') {
      throw new Error(`Missing title in frontmatter for: ${entry.name}`);
    }

    let date: string | undefined;
    if (rawData.date instanceof Date) {
      date = rawData.date.toISOString().split('T')[0];
    } else if (typeof rawData.date === 'string') {
      date = rawData.date;
    }

    let tags: string[] | undefined;
    if (Array.isArray(rawData.tags)) {
      tags = rawData.tags.map((t) => String(t));
    }

    pages.push({
      frontmatter: {
        title: rawData.title,
        date,
        tags,
      },
      content: parsed.content,
      slug,
    });
  }

  pages.sort((a, b) => {
    if (a.frontmatter.date && b.frontmatter.date) {
      return new Date(b.frontmatter.date).getTime() - new Date(a.frontmatter.date).getTime();
    }
    if (a.frontmatter.date) return -1;
    if (b.frontmatter.date) return 1;
    return a.frontmatter.title.localeCompare(b.frontmatter.title);
  });

  return pages;
}

function renderPageTemplate(page: Page): string {
  const htmlContent = marked.parse(page.content, { async: false }) as string;
  const dateStr = page.frontmatter.date
    ? `<p class="date">${page.frontmatter.date}</p>`
    : '';
  const tagsStr =
    page.frontmatter.tags && page.frontmatter.tags.length > 0
      ? `<p class="tags">Tags: ${page.frontmatter.tags.join(', ')}</p>`
      : '';

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${page.frontmatter.title}</title>
</head>
<body>
  <nav><a href="index.html">Home</a></nav>
  <article>
    <h1>${page.frontmatter.title}</h1>
    ${dateStr}
    ${tagsStr}
    <div>${htmlContent}</div>
  </article>
</body>
</html>`;
}

function renderIndexTemplate(pages: Page[]): string {
  const listItems = pages
    .map((page) => {
      const dateStr = page.frontmatter.date
        ? `<span class="date">${page.frontmatter.date}</span>`
        : '';
      return `    <li><a href="${page.slug}.html">${page.frontmatter.title}</a> ${dateStr}</li>`;
    })
    .join('\n');

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>My Site</title>
</head>
<body>
  <h1>All Pages</h1>
  <ul>
${listItems}
  </ul>
</body>
</html>`;
}

export function build(options: BuildOptions): void {
  const { contentDir, outputDir } = options;
  const pages = readPages(contentDir);

  const absOutputDir = path.resolve(outputDir);
  fs.mkdirSync(absOutputDir, { recursive: true });

  for (const page of pages) {
    const html = renderPageTemplate(page);
    const outPath = path.join(absOutputDir, `${page.slug}.html`);
    fs.writeFileSync(outPath, html, 'utf-8');
  }

  const indexHtml = renderIndexTemplate(pages);
  fs.writeFileSync(path.join(absOutputDir, 'index.html'), indexHtml, 'utf-8');
}
