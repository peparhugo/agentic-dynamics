import { promises as fs } from 'node:fs';
import path from 'node:path';
import matter from 'gray-matter';
import { marked } from 'marked';

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
}

export interface GeneratedPage {
  title: string;
  date?: string;
  tags: string[];
  sourcePath: string;
  outputPath: string;
  url: string;
}

interface ParsedPage extends GeneratedPage {
  html: string;
}

const DEFAULT_CONTENT_DIR = './content';
const DEFAULT_OUTPUT_DIR = './dist';

function escapeHtml(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function normalizeDate(value: unknown): string | undefined {
  if (value instanceof Date) {
    return value.toISOString().slice(0, 10);
  }
  if (typeof value === 'string' || typeof value === 'number') {
    return String(value);
  }
  return undefined;
}

function normalizeTags(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.map(String);
  }
  if (typeof value === 'string') {
    return value.split(',').map((tag) => tag.trim()).filter(Boolean);
  }
  return [];
}

async function findMarkdownFiles(directory: string): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry) => {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      return findMarkdownFiles(entryPath);
    }
    return /\.md$/i.test(entry.name) ? [entryPath] : [];
  }));
  return files.flat().sort();
}

function pageTemplate(page: ParsedPage): string {
  const title = escapeHtml(page.title);
  const depth = page.url.split('/').length - 1;
  const homeUrl = `${'../'.repeat(depth)}index.html`;
  const metadata = [
    page.date ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '',
    page.tags.length > 0
      ? `<ul class="tags">${page.tags.map((tag) => `<li>${escapeHtml(tag)}</li>`).join('')}</ul>`
      : '',
  ].filter(Boolean).join('\n');

  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${title}</title>
</head>
<body>
  <nav><a href="${homeUrl}">Home</a></nav>
  <main>
    <article>
      <header><h1>${title}</h1>${metadata ? `\n${metadata}` : ''}</header>
      ${page.html}
    </article>
  </main>
</body>
</html>
`;
}

function indexTemplate(pages: ParsedPage[]): string {
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

export async function buildSite(options: BuildOptions = {}): Promise<GeneratedPage[]> {
  const contentDir = path.resolve(options.contentDir ?? DEFAULT_CONTENT_DIR);
  const outputDir = path.resolve(options.outputDir ?? DEFAULT_OUTPUT_DIR);
  const files = await findMarkdownFiles(contentDir);

  const pages = await Promise.all(files.map(async (sourcePath): Promise<ParsedPage> => {
    const source = await fs.readFile(sourcePath, 'utf8');
    const parsed = matter(source);
    const relativePath = path.relative(contentDir, sourcePath);
    const relativeOutput = relativePath.replace(/\.md$/i, '.html');
    const title = typeof parsed.data.title === 'string'
      ? parsed.data.title
      : path.basename(relativePath, path.extname(relativePath));

    return {
      title,
      date: normalizeDate(parsed.data.date),
      tags: normalizeTags(parsed.data.tags),
      sourcePath,
      outputPath: path.join(outputDir, relativeOutput),
      url: relativeOutput.split(path.sep).join('/'),
      html: await marked.parse(parsed.content),
    };
  }));

  pages.sort((left, right) => {
    if (left.date && right.date && left.date !== right.date) {
      return right.date.localeCompare(left.date);
    }
    if (left.date !== right.date) {
      return left.date ? -1 : 1;
    }
    return left.title.localeCompare(right.title);
  });

  await fs.rm(outputDir, { recursive: true, force: true });
  await Promise.all(pages.map(async (page) => {
    await fs.mkdir(path.dirname(page.outputPath), { recursive: true });
    await fs.writeFile(page.outputPath, pageTemplate(page), 'utf8');
  }));
  await fs.mkdir(outputDir, { recursive: true });
  await fs.writeFile(path.join(outputDir, 'index.html'), indexTemplate(pages), 'utf8');

  return pages.map(({ html: _html, ...page }) => page);
}
