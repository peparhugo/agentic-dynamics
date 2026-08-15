import fs from 'node:fs/promises';
import path from 'node:path';
import { marked } from 'marked';
import { parseMarkdown, Frontmatter } from './parser';

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
}

interface Page {
  source: string;
  url: string;
  data: Frontmatter;
  html: string;
}

function escapeHtml(value: unknown): string {
  return String(value ?? '').replace(/[&<>"']/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[character] as string));
}

function documentHtml(title: string, body: string): string {
  return `<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>${escapeHtml(title)}</title>\n</head>\n<body>\n${body}\n</body>\n</html>\n`;
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

export async function buildSite(options: BuildOptions = {}): Promise<void> {
  const contentDir = path.resolve(options.contentDir ?? './content');
  const outputDir = path.resolve(options.outputDir ?? './dist');
  const files = await markdownFiles(contentDir);
  const pages: Page[] = [];

  await fs.rm(outputDir, { recursive: true, force: true });
  await fs.mkdir(outputDir, { recursive: true });
  for (const source of files) {
    const parsed = parseMarkdown(await fs.readFile(source, 'utf8'));
    const relative = path.relative(contentDir, source);
    const url = relative.replace(/\.md$/i, '.html').split(path.sep).join('/');
    const title = typeof parsed.data.title === 'string' ? parsed.data.title : path.basename(relative, path.extname(relative));
    const tags = Array.isArray(parsed.data.tags) ? parsed.data.tags : [];
    const metadata = [parsed.data.date ? `<time>${escapeHtml(parsed.data.date)}</time>` : '', tags.length ? `<p class="tags">${tags.map(escapeHtml).join(', ')}</p>` : ''].join('');
    const body = `<article>\n<h1>${escapeHtml(title)}</h1>\n${metadata}\n${marked.parse(parsed.content)}\n</article>`;
    const destination = path.join(outputDir, url);
    await fs.mkdir(path.dirname(destination), { recursive: true });
    await fs.writeFile(destination, documentHtml(title, body), 'utf8');
    pages.push({ source, url, data: parsed.data, html: body });
  }

  const listing = pages.map((page) => {
    const title = typeof page.data.title === 'string' ? page.data.title : path.basename(page.url, '.html');
    return `<li><a href="${escapeHtml(page.url)}">${escapeHtml(title)}</a></li>`;
  }).join('\n');
  await fs.writeFile(path.join(outputDir, 'index.html'), documentHtml('Index', `<main>\n<h1>Pages</h1>\n<ul>\n${listing}\n</ul>\n</main>`), 'utf8');
}
