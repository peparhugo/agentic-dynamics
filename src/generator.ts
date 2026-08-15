import fs from 'node:fs/promises';
import path from 'node:path';
import matter from 'gray-matter';
import { marked } from 'marked';

export interface Frontmatter {
  title?: string;
  date?: string;
  tags?: string[];
  [key: string]: unknown;
}

export interface Page {
  slug: string;
  source: string;
  title: string;
  date?: string;
  tags: string[];
  html: string;
}

function parseScalar(value: string): unknown {
  const trimmed = value.trim();
  if (!trimmed) return '';
  if ((trimmed.startsWith('[') && trimmed.endsWith(']'))) {
    return trimmed.slice(1, -1).split(',').map((item) => item.trim()).filter(Boolean);
  }
  if ((trimmed.startsWith('"') && trimmed.endsWith('"')) || (trimmed.startsWith("'") && trimmed.endsWith("'"))) {
    return trimmed.slice(1, -1);
  }
  return trimmed;
}

function parseYamlFrontmatter(source: string): { data: Frontmatter; content: string } | undefined {
  if (!source.startsWith('---')) return undefined;
  const match = source.match(/^---\s*\r?\n([\s\S]*?)\r?\n---\s*\r?\n?/);
  if (!match) return undefined;
  const json = match[1].trim();
  if (json.startsWith('{')) {
    const parsed = matter(source);
    return { data: parsed.data as Frontmatter, content: parsed.content };
  }
  const data: Frontmatter = {};
  for (const line of match[1].split(/\r?\n/)) {
    const separator = line.indexOf(':');
    if (separator < 0) continue;
    const key = line.slice(0, separator).trim();
    if (key) data[key] = parseScalar(line.slice(separator + 1));
  }
  return { data, content: source.slice(match[0].length) };
}

export function parseMarkdown(source: string, sourcePath = 'page.md'): Page {
  const yaml = parseYamlFrontmatter(source);
  const parsed = yaml ? { data: yaml.data, content: matter(yaml.content).content } : matter(source);
  const data = parsed.data as Frontmatter;
  const basename = path.basename(sourcePath, path.extname(sourcePath));
  const tags = Array.isArray(data.tags) ? data.tags.map(String) : data.tags ? String(data.tags).split(',').map((tag) => tag.trim()).filter(Boolean) : [];
  return {
    slug: basename,
    source: sourcePath,
    title: data.title ? String(data.title) : basename,
    date: data.date ? String(data.date) : undefined,
    tags,
    html: String(marked.parse(parsed.content)),
  };
}

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files: string[] = [];
  for (const entry of entries) {
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...await markdownFiles(fullPath));
    else if (/\.md$/i.test(entry.name)) files.push(fullPath);
  }
  return files.sort();
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character]!));
}

function layout(title: string, body: string): string {
  return `<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>${escapeHtml(title)}</title>\n</head>\n<body>\n${body}\n</body>\n</html>\n`;
}

export async function buildSite(contentDir = './content', outputDir = './dist'): Promise<Page[]> {
  const files = await markdownFiles(contentDir);
  const pages = await Promise.all(files.map(async (file) => parseMarkdown(await fs.readFile(file, 'utf8'), path.relative(contentDir, file))));
  pages.sort((a, b) => (b.date || '').localeCompare(a.date || '') || a.title.localeCompare(b.title));
  await fs.mkdir(outputDir, { recursive: true });
  await Promise.all(pages.map((page) => fs.writeFile(path.join(outputDir, `${page.slug}.html`), layout(page.title, `<main>\n<h1>${escapeHtml(page.title)}</h1>\n${page.html}\n</main>`))));
  const links = pages.map((page) => `<li><a href="${encodeURIComponent(page.slug)}.html">${escapeHtml(page.title)}</a>${page.date ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : ''}</li>`).join('\n');
  await fs.writeFile(path.join(outputDir, 'index.html'), layout('Home', `<main>\n<h1>Pages</h1>\n<ul>\n${links}\n</ul>\n</main>`));
  return pages;
}
