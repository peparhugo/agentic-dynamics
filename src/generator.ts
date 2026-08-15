import fs from 'fs';
import path from 'path';
import { renderMarkdownToHtml } from './markdown';
import { TemplateEngine } from './templates';
import { escapeHtml } from './escape';
import type { Page } from './types';

export interface BuildOptions {
  contentDir: string;
  outputDir: string;
  templateDir?: string;
  defaultTemplate?: string;
  defaultLayout?: string;
}

const MARKDOWN_EXTENSIONS = /\.(md|markdown)$/;

export { escapeHtml };

function pageTitle(data: Record<string, unknown>, slug: string): string {
  const title = data.title;
  return typeof title === 'string' && title.trim().length > 0 ? title : slug;
}

function pageDate(data: Record<string, unknown>): string | undefined {
  const date = data.date;
  return typeof date === 'string' && date.length > 0 ? date : undefined;
}

function pageTags(data: Record<string, unknown>): string[] | undefined {
  if (!Array.isArray(data.tags)) {
    return undefined;
  }
  const tags = data.tags.map(String).filter((tag) => tag.trim().length > 0);
  return tags.length > 0 ? tags : undefined;
}

function pageStringField(data: Record<string, unknown>, key: string): string | undefined {
  const value = data[key];
  return typeof value === 'string' && value.trim().length > 0 ? value : undefined;
}

function readPages(contentDir: string): Page[] {
  const entries = fs.readdirSync(contentDir);
  const files = entries.filter((entry) => MARKDOWN_EXTENSIONS.test(entry)).sort();
  const pages: Page[] = [];
  for (const file of files) {
    const raw = fs.readFileSync(path.join(contentDir, file), 'utf8');
    const slug = file.replace(MARKDOWN_EXTENSIONS, '');
    const { data, content, html } = renderMarkdownToHtml(raw);
    pages.push({
      slug,
      title: pageTitle(data, slug),
      date: pageDate(data),
      tags: pageTags(data),
      template: pageStringField(data, 'template'),
      layout: pageStringField(data, 'layout'),
      data,
      contentHtml: html,
      content,
    });
  }
  return pages;
}

export function renderPage(page: Page): string {
  const date = page.date ? `<p class="date">${escapeHtml(page.date)}</p>` : '';
  const tags = page.tags
    ? `<ul class="tags">${page.tags
        .map((tag) => `<li>${escapeHtml(tag)}</li>`)
        .join('')}</ul>`
    : '';
  return [
    '<!DOCTYPE html>',
    '<html lang="en">',
    '<head>',
    '<meta charset="utf-8">',
    '<meta name="viewport" content="width=device-width, initial-scale=1">',
    `<title>${escapeHtml(page.title)}</title>`,
    '</head>',
    '<body>',
    '<header>',
    `<h1>${escapeHtml(page.title)}</h1>`,
    date,
    tags,
    '</header>',
    '<main>',
    page.contentHtml,
    '</main>',
    '</body>',
    '</html>',
    '',
  ].join('\n');
}

function sortPages(pages: Page[]): Page[] {
  return [...pages].sort((a, b) => {
    if (a.date && b.date) {
      return b.date.localeCompare(a.date);
    }
    if (a.date) return -1;
    if (b.date) return 1;
    return a.slug.localeCompare(b.slug);
  });
}

export function renderIndex(pages: Page[]): string {
  const items = sortPages(pages)
    .map((page) => {
      const date = page.date ? ` <span class="date">${escapeHtml(page.date)}</span>` : '';
      return `    <li><a href="${escapeHtml(page.slug)}.html">${escapeHtml(
        page.title
      )}</a>${date}</li>`;
    })
    .join('\n');
  return [
    '<!DOCTYPE html>',
    '<html lang="en">',
    '<head>',
    '<meta charset="utf-8">',
    '<meta name="viewport" content="width=device-width, initial-scale=1">',
    '<title>Index</title>',
    '</head>',
    '<body>',
    '<h1>Index</h1>',
    '<ul>',
    items,
    '</ul>',
    '</body>',
    '</html>',
    '',
  ].join('\n');
}

/**
 * Resolve the template directory. An explicitly requested directory that does
 * not exist is an error; the default `./templates` directory is only used when
 * present so sites without templates keep the built-in rendering.
 */
function resolveTemplateDir(options: BuildOptions): string | null {
  if (options.templateDir !== undefined) {
    const dir = path.resolve(options.templateDir);
    if (!fs.existsSync(dir) || !fs.statSync(dir).isDirectory()) {
      throw new Error(`Template directory does not exist: ${dir}`);
    }
    return dir;
  }
  const dir = path.resolve('templates');
  return fs.existsSync(dir) && fs.statSync(dir).isDirectory() ? dir : null;
}

/**
 * Build the site: every markdown file in `contentDir` becomes a page in
 * `outputDir` and an `index.html` listing all pages is generated.
 * When a template directory exists (default `./templates`), pages are rendered
 * through its Handlebars templates, layouts and partials.
 * Returns the list of generated pages.
 */
export function buildSite(options: BuildOptions): Page[] {
  const contentDir = path.resolve(options.contentDir);
  const outputDir = path.resolve(options.outputDir);

  if (!fs.existsSync(contentDir)) {
    throw new Error(`Content directory does not exist: ${contentDir}`);
  }
  if (!fs.statSync(contentDir).isDirectory()) {
    throw new Error(`Content path is not a directory: ${contentDir}`);
  }

  fs.mkdirSync(outputDir, { recursive: true });

  const templateDir = resolveTemplateDir(options);
  const engine =
    templateDir === null
      ? null
      : new TemplateEngine({
          templateDir,
          defaultTemplate: options.defaultTemplate,
          defaultLayout: options.defaultLayout,
        });

  const pages = readPages(contentDir);
  for (const page of pages) {
    const html = engine && engine.hasContent() ? engine.renderPage(page) : renderPage(page);
    fs.writeFileSync(path.join(outputDir, `${page.slug}.html`), html);
  }
  const indexHtml = engine && engine.hasContent() ? engine.renderIndex(pages) : renderIndex(pages);
  fs.writeFileSync(path.join(outputDir, 'index.html'), indexHtml);
  return pages;
}
