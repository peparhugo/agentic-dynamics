import * as fs from 'fs';
import * as path from 'path';
import { parseMarkdown, Frontmatter } from './markdown';
import { TemplateEngine, RenderContext } from './templates';

export interface Page {
  slug: string;
  title: string;
  date: string | null;
  tags: string[];
  html: string;
  template: string | null;
  layout: string | null;
  frontmatter: Frontmatter;
  sourcePath: string;
  outputPath: string;
}

export interface BuildOptions {
  contentDir: string;
  outputDir: string;
  templatesDir?: string;
}

export interface BuildResult {
  pages: Page[];
  outputDir: string;
  indexPath: string;
}

function collectMarkdownFiles(dir: string): string[] {
  const results: string[] = [];
  if (!fs.existsSync(dir)) {
    return results;
  }
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      results.push(...collectMarkdownFiles(full));
    } else if (entry.isFile() && entry.name.toLowerCase().endsWith('.md')) {
      results.push(full);
    }
  }
  return results;
}

function toSlug(contentDir: string, filePath: string): string {
  const rel = path.relative(contentDir, filePath);
  const ext = path.extname(rel);
  const withoutExt = ext ? rel.slice(0, -ext.length) : rel;
  return withoutExt.split(path.sep).join('/');
}

function normalizeDate(value: unknown): string | null {
  if (value === null || value === undefined) {
    return null;
  }
  if (value instanceof Date) {
    return value.toISOString().slice(0, 10);
  }
  const str = String(value).trim();
  return str.length > 0 ? str : null;
}

function normalizeTags(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.map((v) => String(v).trim()).filter((v) => v.length > 0);
  }
  if (typeof value === 'string') {
    return value
      .split(',')
      .map((v) => v.trim())
      .filter((v) => v.length > 0);
  }
  return [];
}

export function escapeHtml(input: string): string {
  return input
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function relativeIndexLink(outputPath: string): string {
  const dir = path.dirname(outputPath);
  const rel = path.relative(dir, 'index.html');
  return rel.split(path.sep).join('/');
}

function renderMeta(date: string | null, tags: string[]): string {
  const meta: string[] = [];
  if (date) {
    meta.push(
      `<time datetime="${escapeHtml(date)}">${escapeHtml(date)}</time>`
    );
  }
  if (tags.length > 0) {
    meta.push(
      `<ul class="tags">${tags
        .map((tag) => `<li>${escapeHtml(tag)}</li>`)
        .join('')}</ul>`
    );
  }
  return meta.join('\n');
}

function pageContext(page: Page): RenderContext {
  return {
    ...page.frontmatter,
    title: page.title,
    date: page.date,
    tags: page.tags,
    content: page.html,
    slug: page.slug,
    sourcePath: page.sourcePath,
    outputPath: page.outputPath,
    home: relativeIndexLink(page.outputPath),
    meta: renderMeta(page.date, page.tags),
  };
}

function renderPage(page: Page, engine: TemplateEngine): string {
  return engine.render(page.template, page.layout, pageContext(page));
}

function renderIndex(pages: Page[]): string {
  const items = pages
    .map((page) => {
      const date = page.date
        ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(
            page.date
          )}</time>`
        : '';
      const tags = page.tags.length
        ? ` <span class="tags">${page.tags
            .map((tag) => escapeHtml(tag))
            .join(', ')}</span>`
        : '';
      return `<li><a href="${escapeHtml(page.outputPath)}">${escapeHtml(
        page.title
      )}</a>${date}${tags}</li>`;
    })
    .join('\n');

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Index</title>
</head>
<body>
<h1>Index</h1>
<ul>
${items}
</ul>
</body>
</html>
`;
}

function normalizeName(value: unknown): string | null {
  if (typeof value !== 'string') {
    return null;
  }
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

export function build(options: BuildOptions): BuildResult {
  const { contentDir, outputDir } = options;
  const templatesDir = options.templatesDir ?? path.resolve('templates');
  const engine = new TemplateEngine(templatesDir);

  const files = collectMarkdownFiles(contentDir);
  const pages: Page[] = files.map((file) => {
    const raw = fs.readFileSync(file, 'utf8');
    const { frontmatter, html } = parseMarkdown(raw);
    const slug = toSlug(contentDir, file);

    const rawTitle = frontmatter.title;
    const title =
      typeof rawTitle === 'string' && rawTitle.trim().length > 0
        ? rawTitle.trim()
        : slug;

    return {
      slug,
      title,
      date: normalizeDate(frontmatter.date),
      tags: normalizeTags(frontmatter.tags),
      html,
      template: normalizeName(frontmatter.template),
      layout: normalizeName(frontmatter.layout),
      frontmatter,
      sourcePath: file,
      outputPath: `${slug}.html`,
    };
  });

  pages.sort((a, b) => {
    const aDate = a.date;
    const bDate = b.date;
    if (!aDate && !bDate) {
      return a.title.localeCompare(b.title);
    }
    if (!aDate) {
      return 1;
    }
    if (!bDate) {
      return -1;
    }
    return bDate.localeCompare(aDate);
  });

  fs.mkdirSync(outputDir, { recursive: true });

  for (const page of pages) {
    const outFile = path.join(outputDir, page.outputPath);
    fs.mkdirSync(path.dirname(outFile), { recursive: true });
    fs.writeFileSync(outFile, renderPage(page, engine));
  }

  const indexPath = path.join(outputDir, 'index.html');
  fs.writeFileSync(indexPath, renderIndex(pages));

  return { pages, outputDir, indexPath };
}
