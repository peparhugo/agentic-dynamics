import fs from 'node:fs/promises';
import path from 'node:path';
import matter from 'gray-matter';
import { marked } from 'marked';

export interface PageMetadata {
  title: string;
  date?: string;
  tags: string[];
}

export interface Page {
  sourcePath: string;
  outputPath: string;
  metadata: PageMetadata;
  html: string;
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
}

const markdownExtensions = new Set(['.md', '.markdown']);

function escapeHtml(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function stringValue(value: unknown): string | undefined {
  if (value === undefined || value === null) return undefined;
  return value instanceof Date ? value.toISOString().slice(0, 10) : String(value);
}

function getMetadata(data: Record<string, unknown>, sourcePath: string): PageMetadata {
  const fallbackTitle = path.basename(sourcePath, path.extname(sourcePath));
  const tagsValue = data.tags;
  const tags = Array.isArray(tagsValue)
    ? tagsValue.map(String)
    : typeof tagsValue === 'string'
      ? tagsValue.split(',').map((tag) => tag.trim()).filter(Boolean)
      : [];

  return {
    title: stringValue(data.title) ?? fallbackTitle,
    date: stringValue(data.date),
    tags,
  };
}

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files: string[] = [];
  for (const entry of entries) {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...await markdownFiles(entryPath));
    else if (markdownExtensions.has(path.extname(entry.name).toLowerCase())) files.push(entryPath);
  }
  return files.sort((a, b) => a.localeCompare(b));
}

function pageDocument(page: Page): string {
  const { metadata } = page;
  const date = metadata.date ? `<time>${escapeHtml(metadata.date)}</time>` : '';
  const tags = metadata.tags.length
    ? `<ul class="tags">${metadata.tags.map((tag) => `<li>${escapeHtml(tag)}</li>`).join('')}</ul>`
    : '';
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${escapeHtml(metadata.title)}</title>
</head>
<body>
  <main>
    <article>
      <header><h1>${escapeHtml(metadata.title)}</h1>${date}${tags}</header>
      ${page.html}
    </article>
  </main>
</body>
</html>
`;
}

function indexDocument(pages: Page[], outputDir: string): string {
  const items = pages.map((page) => {
    const href = path.relative(outputDir, page.outputPath).replaceAll(path.sep, '/');
    const date = page.metadata.date ? ` <time>${escapeHtml(page.metadata.date)}</time>` : '';
    return `      <li><a href="${escapeHtml(href)}">${escapeHtml(page.metadata.title)}</a>${date}</li>`;
  }).join('\n');
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Index</title>
</head>
<body>
  <main><h1>Pages</h1><ul>${items}</ul></main>
</body>
</html>
`;
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const contentDir = path.resolve(options.contentDir ?? './content');
  const outputDir = path.resolve(options.outputDir ?? './dist');
  const files = await markdownFiles(contentDir);
  const pages: Page[] = [];

  for (const sourcePath of files) {
    const relativePath = path.relative(contentDir, sourcePath);
    const outputPath = path.join(outputDir, relativePath.replace(/\.(md|markdown)$/i, '.html'));
    const parsed = matter(await fs.readFile(sourcePath, 'utf8'));
    pages.push({
      sourcePath,
      outputPath,
      metadata: getMetadata(parsed.data as Record<string, unknown>, sourcePath),
      html: await marked.parse(parsed.content),
    });
  }

  await fs.mkdir(outputDir, { recursive: true });
  for (const page of pages) {
    await fs.mkdir(path.dirname(page.outputPath), { recursive: true });
    await fs.writeFile(page.outputPath, pageDocument(page), 'utf8');
  }
  await fs.writeFile(path.join(outputDir, 'index.html'), indexDocument(pages, outputDir), 'utf8');
  return pages;
}
