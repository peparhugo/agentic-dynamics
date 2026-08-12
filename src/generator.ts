import { promises as fs } from 'node:fs';
import path from 'node:path';
import matter from 'gray-matter';
import { marked } from 'marked';

export interface SiteOptions {
  contentDir?: string;
  outputDir?: string;
}

export interface Page {
  source: string;
  output: string;
  title: string;
  date?: string;
  tags: string[];
  html: string;
}

type Frontmatter = {
  title?: unknown;
  date?: unknown;
  tags?: unknown;
};

const layout = (title: string, body: string): string => `<!doctype html>
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

function escapeHtml(value: string): string {
  return value.replace(/[&<>'"]/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;',
  }[character] ?? character));
}

function metadataValue(value: unknown): string | undefined {
  return value instanceof Date ? value.toISOString().slice(0, 10) :
    typeof value === 'string' || typeof value === 'number' ? String(value) : undefined;
}

function tagsValue(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String);
  if (typeof value === 'string') return value.split(',').map((tag) => tag.trim()).filter(Boolean);
  return [];
}

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files: string[] = [];
  for (const entry of entries) {
    const file = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...await markdownFiles(file));
    else if (entry.isFile() && /\.md$/i.test(entry.name)) files.push(file);
  }
  return files.sort((a, b) => a.localeCompare(b));
}

export async function buildSite(options: SiteOptions = {}): Promise<Page[]> {
  const contentDir = path.resolve(options.contentDir ?? './content');
  const outputDir = path.resolve(options.outputDir ?? './dist');
  const files = await markdownFiles(contentDir);
  const pages: Page[] = [];

  await fs.rm(outputDir, { recursive: true, force: true });
  await fs.mkdir(outputDir, { recursive: true });

  for (const file of files) {
    const parsed = matter(await fs.readFile(file, 'utf8'));
    const metadata = parsed.data as Frontmatter;
    const relative = path.relative(contentDir, file);
    const output = relative.replace(/\.md$/i, '.html');
    const title = metadataValue(metadata.title) ?? path.basename(relative, path.extname(relative));
    const date = metadataValue(metadata.date);
    const tags = tagsValue(metadata.tags);
    const content = await marked.parse(parsed.content);
    const details = [date ? `<time datetime="${escapeHtml(date)}">${escapeHtml(date)}</time>` : '',
      tags.length ? `<ul class="tags">${tags.map((tag) => `<li>${escapeHtml(tag)}</li>`).join('')}</ul>` : '']
      .filter(Boolean).join('\n');
    const body = `<main>\n  <article>\n    <h1>${escapeHtml(title)}</h1>\n    ${details}\n    ${content}  </article>\n</main>`;
    const page = { source: relative, output, title, date, tags, html: layout(title, body) };
    pages.push(page);
    const destination = path.join(outputDir, output);
    await fs.mkdir(path.dirname(destination), { recursive: true });
    await fs.writeFile(destination, page.html, 'utf8');
  }

  const links = pages.map((page) => `    <li><a href="${page.output.split(path.sep).join('/')}">${escapeHtml(page.title)}</a>${page.date ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : ''}</li>`).join('\n');
  const indexBody = `<main>\n  <h1>Pages</h1>\n  <ul>\n${links}\n  </ul>\n</main>`;
  await fs.writeFile(path.join(outputDir, 'index.html'), layout('Pages', indexBody), 'utf8');
  return pages;
}
