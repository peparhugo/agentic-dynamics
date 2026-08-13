import { promises as fs } from 'node:fs';
import path from 'node:path';
import matter from 'gray-matter';
import { marked } from 'marked';

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
}

export interface Page {
  title: string;
  date?: string;
  tags: string[];
  sourcePath: string;
  outputPath: string;
  url: string;
  html: string;
}

const escapeHtml = (value: string): string => value
  .replaceAll('&', '&amp;')
  .replaceAll('<', '&lt;')
  .replaceAll('>', '&gt;')
  .replaceAll('"', '&quot;')
  .replaceAll("'", '&#39;');

function titleFromFilename(filename: string): string {
  const stem = path.basename(filename, path.extname(filename));
  return stem
    .replace(/[-_]+/g, ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function parseDate(value: unknown): string | undefined {
  if (value instanceof Date) {
    return value.toISOString().slice(0, 10);
  }
  if (typeof value === 'string' || typeof value === 'number') {
    return String(value);
  }
  return undefined;
}

function parseTags(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.map(String).map((tag) => tag.trim()).filter(Boolean);
  }
  if (typeof value === 'string') {
    return value.split(',').map((tag) => tag.trim()).filter(Boolean);
  }
  return [];
}

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry) => {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      return markdownFiles(entryPath);
    }
    return /\.md$/i.test(entry.name) ? [entryPath] : [];
  }));
  return files.flat().sort((left, right) => left.localeCompare(right));
}

function document(title: string, body: string): string {
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${escapeHtml(title)}</title>
</head>
<body>
${body}
</body>
</html>
`;
}

function renderPage(page: Page): string {
  const metadata = [
    page.date ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '',
    page.tags.length > 0
      ? `<ul class="tags">${page.tags.map((tag) => `<li>${escapeHtml(tag)}</li>`).join('')}</ul>`
      : ''
  ].filter(Boolean).join('\n');

  return document(page.title, `<main>
  <article>
    <header>
      <h1>${escapeHtml(page.title)}</h1>
      ${metadata}
    </header>
    ${page.html}
  </article>
</main>`);
}

function renderIndex(pages: Page[]): string {
  const items = pages.map((page) => {
    const date = page.date ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '';
    return `    <li><a href="${escapeHtml(page.url)}">${escapeHtml(page.title)}</a>${date}</li>`;
  }).join('\n');

  return document('Pages', `<main>
  <h1>Pages</h1>
  <ul>
${items}
  </ul>
</main>`);
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const contentDir = path.resolve(options.contentDir ?? 'content');
  const outputDir = path.resolve(options.outputDir ?? 'dist');

  let files: string[];
  try {
    files = await markdownFiles(contentDir);
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') {
      throw new Error(`Content directory does not exist: ${contentDir}`);
    }
    throw error;
  }

  const pages = await Promise.all(files.map(async (sourcePath): Promise<Page> => {
    const relativePath = path.relative(contentDir, sourcePath);
    const parsed = matter(await fs.readFile(sourcePath, 'utf8'));
    const outputRelativePath = relativePath.replace(/\.md$/i, '.html');
    const title = typeof parsed.data.title === 'string' && parsed.data.title.trim()
      ? parsed.data.title.trim()
      : titleFromFilename(sourcePath);

    return {
      title,
      date: parseDate(parsed.data.date),
      tags: parseTags(parsed.data.tags),
      sourcePath,
      outputPath: path.join(outputDir, outputRelativePath),
      url: outputRelativePath.split(path.sep).map(encodeURIComponent).join('/'),
      html: await marked.parse(parsed.content)
    };
  }));

  pages.sort((left, right) => {
    if (left.date && right.date && left.date !== right.date) {
      return right.date.localeCompare(left.date);
    }
    return left.title.localeCompare(right.title);
  });

  await fs.mkdir(outputDir, { recursive: true });
  await Promise.all(pages.map(async (page) => {
    await fs.mkdir(path.dirname(page.outputPath), { recursive: true });
    await fs.writeFile(page.outputPath, renderPage(page), 'utf8');
  }));
  await fs.writeFile(path.join(outputDir, 'index.html'), renderIndex(pages), 'utf8');

  return pages;
}
