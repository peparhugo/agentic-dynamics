import fs from 'fs';
import path from 'path';
import { TemplateEngine, TemplateContext } from '../templates';
import type { Plugin, PluginContext } from '../plugin';
import type { Page } from '../types';

const DEFAULT_TEMPLATES_DIR = './templates';

/**
 * Built-in plugin that renders pages through Handlebars templates and layouts
 * when a templates directory exists, otherwise falls back to the built-in
 * HTML renderer. It also writes the site index.
 */
export class TemplatePlugin implements Plugin {
  name = 'template';

  private templatesDir = DEFAULT_TEMPLATES_DIR;
  private engine: TemplateEngine | undefined;
  private useTemplates = false;

  beforeBuild(context: PluginContext): void {
    this.templatesDir = context.options.templatesDir ?? DEFAULT_TEMPLATES_DIR;
    this.engine = new TemplateEngine({ templatesDir: this.templatesDir });
    this.useTemplates = this.engine.hasTemplatesDir();
  }

  onFile(page: Page): void {
    const engine = this.engine!;
    page.html = this.useTemplates ? renderPageWithTemplate(page, engine) : renderPage(page);
  }

  afterBuild(context: PluginContext): void {
    const indexHtml = renderIndex(context.pages);
    fs.writeFileSync(path.join(context.outputDir, 'index.html'), indexHtml);
  }
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
