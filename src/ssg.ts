import fs from 'fs';
import path from 'path';
import { marked } from 'marked';
import { parseMarkdown } from './frontmatter';
import { TemplateEngine, TemplateContext } from './templates';
import type { BuildOptions, BuildResult, Page } from './types';

const MARKDOWN_EXTENSIONS = ['.md', '.markdown'];
const DEFAULT_TEMPLATES_DIR = './templates';

export function build(options: BuildOptions): BuildResult {
  const { contentDir, outputDir } = options;
  const templatesDir = options.templatesDir ?? DEFAULT_TEMPLATES_DIR;
  const pages = readPages(contentDir);

  fs.mkdirSync(outputDir, { recursive: true });

  const engine = new TemplateEngine({ templatesDir });
  const useTemplates = engine.hasTemplatesDir();

  for (const page of pages) {
    const pageHtml = useTemplates ? renderPageWithTemplate(page, engine) : renderPage(page);
    fs.writeFileSync(path.join(outputDir, `${page.slug}.html`), pageHtml);
  }

  const indexHtml = renderIndex(pages);
  fs.writeFileSync(path.join(outputDir, 'index.html'), indexHtml);

  return { pages, outputDir };
}

function readPages(contentDir: string): Page[] {
  if (!fs.existsSync(contentDir)) {
    throw new Error(`Content directory not found: ${contentDir}`);
  }

  const entries = fs.readdirSync(contentDir);
  const pages: Page[] = [];

  for (const entry of entries.sort()) {
    const ext = path.extname(entry);
    if (!MARKDOWN_EXTENSIONS.includes(ext)) continue;

    const filePath = path.join(contentDir, entry);
    const raw = fs.readFileSync(filePath, 'utf-8');
    const { data, content } = parseMarkdown(raw);
    const slug = slugify(entry);

    pages.push({
      slug,
      title: typeof data.title === 'string' && data.title.trim() !== '' ? data.title : slug,
      date: normalizeDate(data.date),
      tags: normalizeTags(data.tags),
      html: marked.parse(content) as string,
      sourcePath: filePath,
      template: typeof data.template === 'string' && data.template.trim() !== '' ? data.template.trim() : undefined,
      layout: typeof data.layout === 'string' && data.layout.trim() !== '' ? data.layout.trim() : undefined,
      data,
    });
  }

  return pages;
}

function slugify(filename: string): string {
  return path.basename(filename, path.extname(filename));
}

function normalizeDate(date: unknown): string | undefined {
  if (typeof date === 'string') return date;
  if (date instanceof Date && !Number.isNaN(date.getTime())) {
    return date.toISOString().slice(0, 10);
  }
  return undefined;
}

function normalizeTags(tags: unknown): string[] {
  if (Array.isArray(tags)) {
    return tags.map((tag) => String(tag).trim()).filter(Boolean);
  }
  if (typeof tags === 'string') {
    return tags
      .split(',')
      .map((tag) => tag.trim())
      .filter(Boolean);
  }
  return [];
}

function renderPageWithTemplate(page: Page, engine: TemplateEngine): string {
  const context: TemplateContext = {
    ...page.data,
    title: page.title,
    date: page.date,
    tags: page.tags,
    slug: page.slug,
    body: page.html,
    content: page.html,
  };

  return engine.render(page.template, page.layout, context);
}

function renderPage(page: Page): string {
  const tagsMarkup = page.tags.length
    ? `<ul class="tags">${page.tags.map((tag) => `<li>${escapeHtml(tag)}</li>`).join('')}</ul>`
    : '';
  const dateMarkup = page.date ? `<p class="date">${escapeHtml(page.date)}</p>` : '';

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${escapeHtml(page.title)}</title>
</head>
<body>
  <header>
    <h1>${escapeHtml(page.title)}</h1>
${dateMarkup}
${tagsMarkup}
  </header>
  <nav><a href="index.html">&larr; All posts</a></nav>
  <article>
${page.html}
  </article>
</body>
</html>
`;
}

function renderIndex(pages: Page[]): string {
  const sorted = [...pages].sort(byDateDesc);
  const items = sorted
    .map((page) => {
      const meta = [page.date, page.tags.length ? page.tags.join(', ') : '']
        .filter(Boolean)
        .join(' \u2014 ');
      const metaMarkup = meta ? ` <span class="meta">${escapeHtml(meta)}</span>` : '';
      return `    <li><a href="${escapeHtml(page.slug)}.html">${escapeHtml(page.title)}</a>${metaMarkup}</li>`;
    })
    .join('\n');

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>All Posts</title>
</head>
<body>
  <header>
    <h1>All Posts</h1>
  </header>
  <ul>
${items}
  </ul>
</body>
</html>
`;
}

function byDateDesc(a: Page, b: Page): number {
  if (!a.date && !b.date) return a.title.localeCompare(b.title);
  if (!a.date) return 1;
  if (!b.date) return -1;
  return b.date.localeCompare(a.date);
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
