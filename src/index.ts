import fs from 'fs';
import path from 'path';
import matter from 'gray-matter';
import { marked } from 'marked';
import { TemplateEngine, DEFAULT_TEMPLATE_NAME, DEFAULT_LAYOUT_NAME } from './templates';

export interface Frontmatter {
  title?: string;
  date?: string;
  tags?: string[];
  template?: string;
  layout?: string | false;
  [key: string]: unknown;
}

export interface Page {
  slug: string;
  title: string;
  date?: string;
  tags: string[];
  html: string;
  sourcePath: string;
  frontmatter: Frontmatter;
  template?: string;
  layout?: string | false;
}

export interface BuildOptions {
  contentDir: string;
  outputDir: string;
  templatesDir?: string;
  defaultTemplate?: string;
  defaultLayout?: string;
}

export interface Site {
  pages: Page[];
  outputDir: string;
}

const DEFAULT_CONTENT_DIR = 'content';
const DEFAULT_OUTPUT_DIR = 'dist';
const DEFAULT_TEMPLATES_DIR = 'templates';

// Matches a YAML frontmatter block. The opening `---` may be preceded only by
// optional leading whitespace so that marked never sees the delimiters.
const FRONTMATTER_REGEX = /^\s*---[ \t]*\r?\n([\s\S]*?)\r?\n---[ \t]*\r?\n?/;

/**
 * Split raw markdown into frontmatter data and the markdown body.
 *
 * The frontmatter block is stripped manually with a regex before the body is
 * handed to `marked`, otherwise `marked` renders the `---` delimiters as a
 * literal horizontal rule. gray-matter is used only to parse the YAML data.
 */
export function splitFrontmatter(raw: string): { data: Frontmatter; body: string } {
  const match = raw.match(FRONTMATTER_REGEX);
  if (!match) {
    return { data: {}, body: raw };
  }

  let data: Frontmatter = {};
  try {
    // gray-matter requires the opening `---` to be the very first bytes of its
    // input, so rebuild a clean block (leading whitespace already stripped).
    data = (matter(`---\n${match[1]}\n---`).data as Frontmatter) ?? {};
  } catch {
    data = {};
  }

  const body = raw.slice(match[0].length);
  return { data, body };
}

function normalizeDate(value: unknown): string | undefined {
  if (value == null) return undefined;
  if (value instanceof Date) {
    return value.toISOString().slice(0, 10);
  }
  const str = String(value).trim();
  return str.length > 0 ? str : undefined;
}

/**
 * Parse raw markdown (with optional frontmatter) into frontmatter data and
 * rendered HTML. The returned HTML is a document fragment (no <html>/<body>).
 */
export function parseMarkdown(raw: string): { frontmatter: Frontmatter; html: string } {
  const { data, body } = splitFrontmatter(raw);
  const html = marked.parse(body, { async: false }) as string;
  return {
    frontmatter: { ...data, date: normalizeDate(data.date) },
    html,
  };
}

export function escapeHtml(input: string): string {
  return input
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function normalizeTags(tags: unknown): string[] {
  if (Array.isArray(tags)) {
    return tags.map((t) => String(t));
  }
  if (typeof tags === 'string') {
    return tags
      .split(',')
      .map((t) => t.trim())
      .filter((t) => t.length > 0);
  }
  return [];
}

function defaultTitle(slug: string): string {
  return slug
    .split(/[/\\-]/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function listMarkdownFiles(dir: string): string[] {
  if (!fs.existsSync(dir)) {
    return [];
  }
  const results: string[] = [];
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      results.push(...listMarkdownFiles(full));
    } else if (entry.isFile() && entry.name.toLowerCase().endsWith('.md')) {
      results.push(full);
    }
  }
  return results;
}

function deriveSlug(filePath: string, contentDir: string): string {
  const relative = path.relative(contentDir, filePath);
  const parsed = path.parse(relative);
  return path.join(parsed.dir, parsed.name).split(path.sep).join('/');
}

function pageSummary(page: Page): Record<string, unknown> {
  return {
    slug: page.slug,
    title: page.title,
    date: page.date,
    tags: page.tags,
    url: `${page.slug}.html`,
  };
}

function buildPageContext(page: Page, pages: Page[]): Record<string, unknown> {
  return {
    ...page.frontmatter,
    title: page.title,
    date: page.date,
    tags: page.tags,
    slug: page.slug,
    content: page.html,
    body: page.html,
    site: {
      pages: pages.map(pageSummary),
    },
  };
}

function renderIndex(pages: Page[]): string {
  const items = pages
    .map((page) => {
      const date = page.date ? ` <span class="date">${escapeHtml(page.date)}</span>` : '';
      return `<li><a href="${escapeHtml(page.slug)}.html">${escapeHtml(
        page.title
      )}</a>${date}</li>`;
    })
    .join('\n');

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Index</title>
</head>
<body>
<h1>All Pages</h1>
<ul>
${items}
</ul>
</body>
</html>
`;
}

/**
 * Build the static site: read markdown from contentDir and write HTML files
 * (one per page plus an index.html) into outputDir.
 */
export function buildSite(options: BuildOptions): Site {
  const contentDir = path.resolve(options.contentDir ?? DEFAULT_CONTENT_DIR);
  const outputDir = path.resolve(options.outputDir ?? DEFAULT_OUTPUT_DIR);
  const templatesDir = options.templatesDir ?? DEFAULT_TEMPLATES_DIR;

  const files = listMarkdownFiles(contentDir).sort();

  const pages: Page[] = files.map((file) => {
    const raw = fs.readFileSync(file, 'utf8');
    const { frontmatter, html } = parseMarkdown(raw);
    const slug = deriveSlug(file, contentDir);
    return {
      slug,
      title: frontmatter.title ?? defaultTitle(slug),
      date: frontmatter.date != null ? String(frontmatter.date) : undefined,
      tags: normalizeTags(frontmatter.tags),
      html,
      sourcePath: file,
      frontmatter,
      template: typeof frontmatter.template === 'string' ? frontmatter.template : undefined,
      layout: frontmatter.layout,
    };
  });

  pages.sort((a, b) => {
    if (a.date && b.date) {
      return b.date.localeCompare(a.date);
    }
    if (a.date) return -1;
    if (b.date) return 1;
    return a.title.localeCompare(b.title);
  });

  fs.mkdirSync(outputDir, { recursive: true });

  const engine = new TemplateEngine(templatesDir, {
    defaultTemplate: options.defaultTemplate ?? DEFAULT_TEMPLATE_NAME,
    defaultLayout: options.defaultLayout ?? DEFAULT_LAYOUT_NAME,
  });

  for (const page of pages) {
    const rendered = engine.render(page.template, page.layout, buildPageContext(page, pages));
    const outFile = path.join(outputDir, `${page.slug}.html`);
    fs.mkdirSync(path.dirname(outFile), { recursive: true });
    fs.writeFileSync(outFile, rendered);
  }

  fs.writeFileSync(path.join(outputDir, 'index.html'), renderIndex(pages));

  return { pages, outputDir };
}
