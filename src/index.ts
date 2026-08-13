import { promises as fs } from 'node:fs';
import path from 'node:path';
import matter from 'gray-matter';
import MarkdownIt from 'markdown-it';
import { parse as parseYaml } from 'yaml';

export interface Frontmatter {
  title?: string;
  date?: string;
  tags?: string[];
}

export interface Page {
  title: string;
  date?: string;
  tags: string[];
  sourcePath: string;
  outputName: string;
  html: string;
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
}

const markdown = new MarkdownIt({ html: false });

function renderMarkdown(source: string): string {
  const embeddedHtml: string[] = [];
  const codePattern = /(```[\s\S]*?```|~~~[\s\S]*?~~~|`+[^`\n]*`+)/g;
  const tokenized = source.split(codePattern).map((segment, index) => {
    if (index % 2 === 1) return segment;
    return segment.replace(/<!--[\s\S]*?-->|<\/?[A-Za-z][^>]*>/g, (tag) => {
      const token = `SSGRAWHTMLTOKEN${embeddedHtml.length}ENDTOKEN`;
      embeddedHtml.push(tag);
      return token;
    });
  }).join('');
  const rendered = markdown.render(tokenized);
  return rendered.replace(/SSGRAWHTMLTOKEN(\d+)ENDTOKEN/g, (_token, index: string) =>
    embeddedHtml[Number(index)] ?? '');
}

function parseFrontmatter(source: string): { content: string; data: Frontmatter } {
  const parsed = matter(source, {
    engines: {
      yaml: (text: string): Record<string, unknown> =>
        parseYaml(text, { schema: 'failsafe' }) as Record<string, unknown>,
    },
  });
  const raw = parsed.data as Record<string, unknown>;
  const tags = Array.isArray(raw.tags)
    ? raw.tags.map(String)
    : typeof raw.tags === 'string'
      ? raw.tags.split(',').map((tag) => tag.trim()).filter(Boolean)
      : [];

  return {
    content: parsed.content,
    data: {
      title: typeof raw.title === 'string' ? raw.title : undefined,
      date: typeof raw.date === 'string' ? raw.date : undefined,
      tags,
    },
  };
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function formatDate(value: string | undefined): string | undefined {
  if (!value) return undefined;
  const match = /^(\d{4})-(\d{2})-(\d{2})(?:T.*)?$/.exec(value);
  if (!match) return value;
  const date = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])));
  return new Intl.DateTimeFormat('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    timeZone: 'UTC',
  }).format(date);
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

export function parsePage(source: string, sourcePath: string): Page {
  const { content, data } = parseFrontmatter(source);
  const baseName = path.basename(sourcePath, path.extname(sourcePath));
  const title = data.title ?? baseName;
  return {
    title,
    date: data.date,
    tags: data.tags ?? [],
    sourcePath,
    outputName: `${baseName === 'index' ? 'index-page' : baseName}.html`,
    html: renderMarkdown(content),
  };
}

export function renderPage(page: Page): string {
  const metadata = [
    page.date ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(formatDate(page.date) ?? page.date)}</time>` : '',
    page.tags.length > 0 ? `<p class="tags">${page.tags.map(escapeHtml).join(', ')}</p>` : '',
  ].filter(Boolean).join('\n');
  return document(page.title, `<main>
  <article>
    <h1>${escapeHtml(page.title)}</h1>
    ${metadata}
    ${page.html}
  </article>
</main>`);
}

export function renderIndex(pages: Page[]): string {
  const items = pages.map((page) => {
    const date = page.date ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(formatDate(page.date) ?? page.date)}</time>` : '';
    return `    <li><a href="${encodeURIComponent(page.outputName)}">${escapeHtml(page.title)}</a>${date}</li>`;
  }).join('\n');
  return document('Pages', `<main>
  <h1>Pages</h1>
  <ul>
${items}
  </ul>
</main>`);
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const contentDir = path.resolve(options.contentDir ?? './content');
  const outputDir = path.resolve(options.outputDir ?? './dist');
  const entries = await fs.readdir(contentDir, { withFileTypes: true });
  const markdownFiles = entries
    .filter((entry) => entry.isFile() && /\.md$/i.test(entry.name))
    .map((entry) => entry.name)
    .sort();

  const pages = await Promise.all(markdownFiles.map(async (fileName) => {
    const sourcePath = path.join(contentDir, fileName);
    return parsePage(await fs.readFile(sourcePath, 'utf8'), sourcePath);
  }));
  pages.sort((a, b) => (b.date ?? '').localeCompare(a.date ?? '') || a.title.localeCompare(b.title));

  await fs.mkdir(outputDir, { recursive: true });
  await Promise.all(pages.map((page) => fs.writeFile(
    path.join(outputDir, page.outputName),
    renderPage(page),
    'utf8',
  )));
  await fs.writeFile(path.join(outputDir, 'index.html'), renderIndex(pages), 'utf8');
  return pages;
}
