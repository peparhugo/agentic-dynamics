import { readdir, readFile, rm, mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import matter from 'gray-matter';
import { marked } from 'marked';

export interface PageMetadata {
  title?: string;
  date?: string;
  tags: string[];
  [key: string]: unknown;
}

export interface Page {
  sourcePath: string;
  outputPath: string;
  url: string;
  metadata: PageMetadata;
  content: string;
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
}

const escapeHtml = (value: string): string => value
  .replaceAll('&', '&amp;')
  .replaceAll('<', '&lt;')
  .replaceAll('>', '&gt;')
  .replaceAll('"', '&quot;')
  .replaceAll("'", '&#39;');

const displayTitle = (page: Page): string => page.metadata.title ||
  path.basename(page.sourcePath, path.extname(page.sourcePath));

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await readdir(directory, { withFileTypes: true });
  const files: string[] = [];
  for (const entry of entries) {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      files.push(...await markdownFiles(entryPath));
    } else if (entry.isFile() && path.extname(entry.name).toLowerCase() === '.md') {
      files.push(entryPath);
    }
  }
  return files.sort();
}

async function loadPage(sourcePath: string, contentDir: string, outputDir: string): Promise<Page> {
  const source = await readFile(sourcePath, 'utf8');
  const parsed = matter(source);
  const rawTags = parsed.data.tags;
  const tags = Array.isArray(rawTags)
    ? rawTags.map(String)
    : typeof rawTags === 'string' ? rawTags.split(',').map((tag) => tag.trim()).filter(Boolean) : [];
  const relativePath = path.relative(contentDir, sourcePath);
  const outputRelativePath = relativePath.replace(/\.md$/i, '.html');
  const outputPath = path.join(outputDir, outputRelativePath);
  const url = `/${outputRelativePath.split(path.sep).join('/')}`;
  return {
    sourcePath,
    outputPath,
    url,
    metadata: { ...parsed.data, tags },
    content: await marked.parse(parsed.content)
  };
}

const renderPage = (page: Page): string => {
  const title = escapeHtml(displayTitle(page));
  const date = page.metadata.date ? `<time>${escapeHtml(String(page.metadata.date))}</time>` : '';
  const tags = page.metadata.tags.length > 0
    ? `<ul class="tags">${page.metadata.tags.map((tag) => `<li>${escapeHtml(tag)}</li>`).join('')}</ul>`
    : '';
  return `<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>${title}</title></head>
<body><main><h1>${title}</h1>${date}${tags}<article>${page.content}</article></main></body>
</html>
`;
};

const renderIndex = (pages: Page[]): string => `<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Index</title></head>
<body><main><h1>Pages</h1><ul>${pages.map((page) =>
  `<li><a href="${escapeHtml(page.url)}">${escapeHtml(displayTitle(page))}</a></li>`).join('')}
</ul></main></body>
</html>
`;

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const contentDir = path.resolve(options.contentDir || './content');
  const outputDir = path.resolve(options.outputDir || './dist');
  const sources = await markdownFiles(contentDir);
  const pages = await Promise.all(sources.map((source) => loadPage(source, contentDir, outputDir)));
  pages.sort((a, b) => displayTitle(a).localeCompare(displayTitle(b)));

  await rm(outputDir, { recursive: true, force: true });
  await mkdir(outputDir, { recursive: true });
  await Promise.all(pages.map(async (page) => {
    await mkdir(path.dirname(page.outputPath), { recursive: true });
    await writeFile(page.outputPath, renderPage(page), 'utf8');
  }));
  await writeFile(path.join(outputDir, 'index.html'), renderIndex(pages), 'utf8');
  return pages;
}
