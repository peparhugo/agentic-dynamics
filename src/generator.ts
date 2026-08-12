import fs from 'node:fs';
import path from 'node:path';
import matter from 'gray-matter';
import { marked } from 'marked';

export interface Page {
  title: string;
  date?: string;
  tags: string[];
  slug: string;
  html: string;
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
}

function markdownFiles(directory: string): string[] {
  if (!fs.existsSync(directory)) return [];
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const filename = path.join(directory, entry.name);
    return entry.isDirectory() ? markdownFiles(filename) : /\.md$/i.test(entry.name) ? [filename] : [];
  });
}

function asDate(value: unknown): number {
  const time = value instanceof Date ? value.getTime() : Date.parse(String(value ?? ''));
  return Number.isNaN(time) ? 0 : time;
}

function pageFromFile(filename: string, contentDir: string): Page {
  const parsed = matter(fs.readFileSync(filename, 'utf8'));
  const relative = path.relative(contentDir, filename);
  const slug = relative.replace(/\.md$/i, '').split(path.sep).join('/');
  const title = typeof parsed.data.title === 'string' ? parsed.data.title : path.basename(slug);
  const rawTags = parsed.data.tags;
  const tags = Array.isArray(rawTags) ? rawTags.map(String) : typeof rawTags === 'string' ? rawTags.split(',').map((tag) => tag.trim()).filter(Boolean) : [];
  return {
    title,
    date: parsed.data.date instanceof Date ? parsed.data.date.toISOString() : parsed.data.date == null ? undefined : String(parsed.data.date),
    tags,
    slug,
    html: marked.parse(parsed.content) as string
  };
}

function document(title: string, body: string): string {
  return `<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>${title}</title>\n</head>\n<body>\n${body}\n</body>\n</html>\n`;
}

export function buildSite(options: BuildOptions = {}): Page[] {
  const contentDir = path.resolve(options.contentDir ?? './content');
  const outputDir = path.resolve(options.outputDir ?? './dist');
  const pages = markdownFiles(contentDir)
    .map((filename) => pageFromFile(filename, contentDir))
    .sort((a, b) => asDate(b.date) - asDate(a.date));

  fs.rmSync(outputDir, { recursive: true, force: true });
  fs.mkdirSync(outputDir, { recursive: true });
  for (const page of pages) {
    const target = path.join(outputDir, `${page.slug}.html`);
    fs.mkdirSync(path.dirname(target), { recursive: true });
    const tags = page.tags.length > 0 ? `<p class="tags">Tags: ${page.tags.join(', ')}</p>\n` : '';
    fs.writeFileSync(target, document(page.title, `<article>\n<h1>${page.title}</h1>\n${tags}${page.html}\n</article>`));
  }
  const items = pages.map((page) => `<li><a href="${page.slug}.html">${page.title}</a>${page.date ? ` <time>${page.date}</time>` : ''}${page.tags.length ? ` <span class="tags">${page.tags.join(', ')}</span>` : ''}</li>`).join('\n');
  fs.writeFileSync(path.join(outputDir, 'index.html'), document('Index', `<main>\n<h1>Pages</h1>\n<ul>\n${items}\n</ul>\n</main>`));
  return pages;
}
