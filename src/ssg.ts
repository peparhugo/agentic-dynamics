import * as fs from 'fs';
import * as path from 'path';
import { marked } from 'marked';
import { parseFrontmatter, type Frontmatter } from './frontmatter.js';

export interface PageMetadata {
  slug: string;
  title: string;
  date?: string;
  tags?: string[];
  [key: string]: unknown;
}

export interface Page {
  metadata: PageMetadata;
  html: string;
}

function ensureDirectoryExists(dir: string): void {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
}

function getMarkdownFiles(contentDir: string): string[] {
  if (!fs.existsSync(contentDir)) {
    return [];
  }

  const entries = fs.readdirSync(contentDir, { withFileTypes: true });
  const files: string[] = [];

  for (const entry of entries) {
    if (entry.isFile() && entry.name.endsWith('.md')) {
      files.push(path.join(contentDir, entry.name));
    }
  }

  return files;
}

function slugify(filename: string): string {
  return filename.replace(/\.md$/, '').toLowerCase().replace(/[^a-z0-9]+/g, '-');
}

function parseMarkdownFile(filePath: string): Page {
  const content = fs.readFileSync(filePath, 'utf-8');
  const { data, content: markdown } = parseFrontmatter(content);
  const html = marked(markdown);

  const filename = path.basename(filePath);
  const slug = slugify(filename);

  const metadata: PageMetadata = {
    slug,
    title: (data.title as string) || slug,
    ...(data.date && { date: data.date }),
    ...(data.tags && { tags: data.tags }),
  };

  return {
    metadata,
    html,
  };
}

function renderPageTemplate(page: Page): string {
  const { metadata, html } = page;
  const dateStr = metadata.date ? `<meta name="date" content="${metadata.date}">` : '';
  const tagsStr = metadata.tags
    ? `<meta name="tags" content="${(metadata.tags as string[]).join(', ')}">`
    : '';

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${metadata.title}</title>
  ${dateStr}
  ${tagsStr}
</head>
<body>
  <header>
    <a href="/index.html">← Home</a>
  </header>
  <article>
    <h1>${metadata.title}</h1>
    ${metadata.date ? `<p class="date">${metadata.date}</p>` : ''}
    ${metadata.tags ? `<p class="tags">Tags: ${(metadata.tags as string[]).join(', ')}</p>` : ''}
    ${html}
  </article>
</body>
</html>`;
}

function renderIndexTemplate(pages: Page[]): string {
  const pageLinks = pages
    .map(
      (page) =>
        `<li><a href="${page.metadata.slug}.html">${page.metadata.title}</a>${page.metadata.date ? ` (${page.metadata.date})` : ''}</li>`
    )
    .join('\n');

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Home</title>
</head>
<body>
  <header>
    <h1>Welcome</h1>
  </header>
  <main>
    <ul>
      ${pageLinks}
    </ul>
  </main>
</body>
</html>`;
}

export function build(contentDir: string, outputDir: string): void {
  ensureDirectoryExists(outputDir);

  const markdownFiles = getMarkdownFiles(contentDir);

  if (markdownFiles.length === 0) {
    fs.writeFileSync(
      path.join(outputDir, 'index.html'),
      `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Home</title>
</head>
<body>
  <h1>Welcome</h1>
  <p>No pages found.</p>
</body>
</html>`
    );
    return;
  }

  const pages = markdownFiles.map((file) => parseMarkdownFile(file));

  pages.forEach((page) => {
    const htmlContent = renderPageTemplate(page);
    const outputFile = path.join(outputDir, `${page.metadata.slug}.html`);
    fs.writeFileSync(outputFile, htmlContent);
  });

  const indexHtml = renderIndexTemplate(pages);
  fs.writeFileSync(path.join(outputDir, 'index.html'), indexHtml);
}
