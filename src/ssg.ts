import fs from 'fs';
import path from 'path';
import matter from 'gray-matter';
import { marked } from 'marked';
import {
  DEFAULT_LAYOUT,
  DEFAULT_TEMPLATE,
  DEFAULT_TEMPLATES_DIR,
  loadTemplates,
  renderTemplateFile,
  TemplateSet,
} from './templates';

marked.setOptions({ gfm: true, headerIds: false });

export const DEFAULT_CONTENT_DIR = './content';
export const DEFAULT_OUTPUT_DIR = './dist';
export { DEFAULT_TEMPLATES_DIR, DEFAULT_TEMPLATE, DEFAULT_LAYOUT } from './templates';

/** Delimiters used to mark a frontmatter block inside a Markdown file. */
export const FRONTMATTER_DELIMITERS: [string, string] = ['<!--', '-->'];

export interface Page {
  /** Filename-derived identifier (e.g. `my-post` for `my-post.md`). */
  slug: string;
  /** Page title from frontmatter, falling back to the slug. */
  title: string;
  /** Optional publication date from frontmatter. */
  date?: string;
  /** Tags listed in frontmatter. */
  tags: string[];
  /** Body rendered from Markdown to HTML. */
  html: string;
  /** Raw Markdown source (frontmatter stripped). */
  markdown: string;
  /** All raw frontmatter fields, exposed to templates. */
  data: Record<string, unknown>;
  /** Template name from frontmatter (`template:`). */
  template?: string;
  /** Layout name from frontmatter (`layout:`). */
  layout?: string;
}

/**
 * Parse a Markdown file that carries frontmatter between HTML comments:
 *
 *     <!--
 *     title: My Post
 *     date: 2024-01-15
 *     tags: [a, b]
 *     -->
 *
 * gray-matter is configured with the comment markers as its delimiters so it
 * only reads the fields found between them.
 */
export function parseMarkdown(raw: string, slug: string): Page {
  const { data, content } = matter(raw, { delimiters: FRONTMATTER_DELIMITERS });

  const title = typeof data.title === 'string' && data.title.trim() !== ''
    ? data.title
    : slug;

  let date: string | undefined;
  if (data.date !== undefined && data.date !== null && String(data.date).trim() !== '') {
    date = data.date instanceof Date
      ? data.date.toISOString().slice(0, 10)
      : String(data.date);
  }

  const tags = Array.isArray(data.tags)
    ? data.tags.map((tag: unknown) => String(tag))
    : [];

  const template =
    typeof data.template === 'string' && data.template.trim() !== ''
      ? data.template.trim()
      : undefined;
  const layout =
    typeof data.layout === 'string' && data.layout.trim() !== ''
      ? data.layout.trim()
      : undefined;

  const html = marked.parse(content) as string;

  return { slug, title, date, tags, html, markdown: content, data, template, layout };
}

/** Read every `.md` file in the content directory and parse it into a Page. */
export function readPages(contentDir: string): Page[] {
  if (!fs.existsSync(contentDir)) {
    throw new Error(`Content directory not found: ${contentDir}`);
  }

  const entries = fs.readdirSync(contentDir, { withFileTypes: true });
  const files = entries
    .filter((entry) => entry.isFile() && entry.name.toLowerCase().endsWith('.md'))
    .sort((a, b) => a.name.localeCompare(b.name));

  return files.map((entry) => {
    const slug = path.basename(entry.name, path.extname(entry.name));
    const raw = fs.readFileSync(path.join(contentDir, entry.name), 'utf8');
    return parseMarkdown(raw, slug);
  });
}

/** Sort pages newest-first by date, keeping other ordering stable. */
export function sortPages(pages: Page[]): Page[] {
  return [...pages].sort((a, b) => {
    if (a.date && b.date) return b.date.localeCompare(a.date);
    if (a.date) return -1;
    if (b.date) return 1;
    return 0;
  });
}

/** Escape a value for safe inclusion in HTML. */
export function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/** Build the context object handed to page templates and layouts. */
export function pageContext(page: Page): Record<string, unknown> {
  return {
    ...page.data,
    slug: page.slug,
    title: page.title,
    date: page.date,
    tags: page.tags,
    html: page.html,
    markdown: page.markdown,
  };
}

/**
 * Render a page through its template and layout. Falls back to the legacy
 * standalone `renderPage` output when no matching template is available.
 */
export function renderPageWithTemplates(page: Page, templates: TemplateSet): string {
  const templateName = page.template ?? DEFAULT_TEMPLATE;
  if (page.template !== undefined && !templates.templates.has(templateName)) {
    throw new Error(`Template not found: ${templateName}`);
  }

  const template = templates.templates.get(templateName);
  if (!template) return renderPage(page);

  const partials = [...templates.partials.values()];
  const content = renderTemplateFile(template, pageContext(page), partials);

  const layoutName = page.layout ?? DEFAULT_LAYOUT;
  if (page.layout !== undefined && !templates.layouts.has(layoutName)) {
    throw new Error(`Layout not found: ${layoutName}`);
  }

  const layout = templates.layouts.get(layoutName);
  if (!layout) return content;

  const context = { ...pageContext(page), body: content };
  return renderTemplateFile(layout, context, partials);
}

/**
 * Render the index page through the `index` template (if any), wrapped in the
 * default layout. Falls back to the legacy `renderIndex` output otherwise.
 */
export function renderIndexWithTemplates(pages: Page[], templates: TemplateSet): string {
  const template = templates.templates.get('index');
  if (!template) return renderIndex(pages);

  const partials = [...templates.partials.values()];
  const context: Record<string, unknown> = { pages: pages.map(pageContext) };
  const content = renderTemplateFile(template, context, partials);

  const layout = templates.layouts.get(DEFAULT_LAYOUT);
  if (!layout) return content;

  return renderTemplateFile(layout, { ...context, body: content }, partials);
}

/** Wrap page content in a full standalone HTML document. */
export function renderPage(page: Page): string {
  const title = escapeHtml(page.title);
  const tagLine = page.tags.length > 0
    ? `<p class="tags">Tags: ${page.tags.map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`).join(' ')}</p>`
    : '';

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${title}</title>
</head>
<body>
<article>
<h1>${title}</h1>
${page.date ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : ''}
${tagLine}
${page.html}
</article>
</body>
</html>
`;
}

/** Render the site index page linking to every generated page. */
export function renderIndex(pages: Page[]): string {
  const listItems = pages
    .map((page) => {
      const date = page.date ? ` &mdash; <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '';
      return `  <li><a href="${escapeHtml(page.slug)}.html">${escapeHtml(page.title)}</a>${date}</li>`;
    })
    .join('\n');

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Home</title>
</head>
<body>
<main>
<h1>Pages</h1>
<ul>
${listItems}
</ul>
</main>
</body>
</html>
`;
}

/**
 * Generate the whole site: read Markdown from `contentDir`, write one HTML
 * file per page into `outputDir` plus an `index.html`. When a `templatesDir`
 * contains page templates, pages and the index are rendered through the
 * template engine (with layouts and partials); otherwise the legacy built-in
 * renderers are used. Returns the pages.
 */
export function build(
  contentDir: string = DEFAULT_CONTENT_DIR,
  outputDir: string = DEFAULT_OUTPUT_DIR,
  templatesDir: string = DEFAULT_TEMPLATES_DIR
): Page[] {
  const pages = sortPages(readPages(contentDir));
  const templates = loadTemplates(templatesDir);
  const useTemplates = templates.templates.size > 0;

  fs.mkdirSync(outputDir, { recursive: true });

  for (const page of pages) {
    const html = useTemplates
      ? renderPageWithTemplates(page, templates)
      : renderPage(page);
    fs.writeFileSync(path.join(outputDir, `${page.slug}.html`), html, 'utf8');
  }

  const indexHtml = useTemplates
    ? renderIndexWithTemplates(pages, templates)
    : renderIndex(pages);
  fs.writeFileSync(path.join(outputDir, 'index.html'), indexHtml, 'utf8');

  return pages;
}
