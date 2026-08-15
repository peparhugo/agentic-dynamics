import fs from 'fs';
import path from 'path';
import Handlebars from 'handlebars';
import { escapeHtml } from './escape';
import type { Page, PageContext } from './types';

export interface TemplateEngineOptions {
  templateDir: string;
  defaultTemplate?: string;
  defaultLayout?: string;
}

const HBS_EXTENSION = /\.hbs$/i;

interface CompiledTemplate {
  name: string;
  source: string;
  render: Handlebars.TemplateDelegate;
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function stringValue(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim().length > 0 ? value : undefined;
}

function resolveName(explicit: string | undefined, fallback: string): string {
  return explicit && explicit.trim().length > 0 ? explicit : fallback;
}

/**
 * Load every `*.hbs` file in `dir` into `target`, keyed by filename without
 * its extension. Missing directories are treated as empty.
 */
function loadTemplatesFromDirectory(
  dir: string,
  target: Map<string, CompiledTemplate>
): void {
  if (!fs.existsSync(dir) || !fs.statSync(dir).isDirectory()) {
    return;
  }
  for (const entry of fs.readdirSync(dir).sort()) {
    if (!HBS_EXTENSION.test(entry)) {
      continue;
    }
    const filePath = path.join(dir, entry);
    if (!fs.statSync(filePath).isFile()) {
      continue;
    }
    const name = entry.replace(HBS_EXTENSION, '');
    const source = fs.readFileSync(filePath, 'utf8');
    target.set(name, { name, source, render: Handlebars.compile(source) });
  }
}

/**
 * Build the context handed to templates: frontmatter data merged with derived
 * page fields. `body`/`contentHtml` hold the rendered markdown so templates
 * can inject it unescaped with `{{{body}}}` / `{{{contentHtml}}}`.
 */
function buildPageContext(page: Page): PageContext {
  const data = isRecord(page.data) ? page.data : {};
  const context: PageContext = {
    ...data,
    slug: page.slug,
    title: page.title,
    date: page.date,
    tags: page.tags,
    content: page.content,
    contentHtml: page.contentHtml,
    body: page.contentHtml,
  };
  return context;
}

/**
 * Default body used when a page does not resolve to a page template but a
 * layout still needs wrapping. Mirrors the built-in `renderPage` body so
 * templated and non-templated output stay consistent.
 */
function renderDefaultBody(page: Page): string {
  const date = page.date ? `<p class="date">${escapeHtml(page.date)}</p>` : '';
  const tags = page.tags
    ? `<ul class="tags">${page.tags
        .map((tag) => `<li>${escapeHtml(tag)}</li>`)
        .join('')}</ul>`
    : '';
  return [
    '<header>',
    `<h1>${escapeHtml(page.title)}</h1>`,
    date,
    tags,
    '</header>',
    '<main>',
    page.contentHtml,
    '</main>',
  ].join('\n');
}

/**
 * Complete built-in page used when neither a template nor a layout resolves,
 * so the output is always a well-formed HTML document.
 */
function renderBuiltInPage(page: Page): string {
  return [
    '<!DOCTYPE html>',
    '<html lang="en">',
    '<head>',
    '<meta charset="utf-8">',
    '<meta name="viewport" content="width=device-width, initial-scale=1">',
    `<title>${escapeHtml(page.title)}</title>`,
    '</head>',
    '<body>',
    renderDefaultBody(page),
    '</body>',
    '</html>',
    '',
  ].join('\n');
}

/**
 * Handlebars template engine for the static site generator.
 *
 * Directory layout (default `./templates`):
 *   templates/            page templates        -> `templates/<name>.hbs`
 *   templates/layouts/    layout templates      -> `templates/layouts/<name>.hbs`
 *   templates/partials/   reusable partials     -> `{{> <name>}}`
 *
 * A page selects a template/layout through its frontmatter (`template`,
 * `layout`); when absent the `default` template/layout is used.
 */
export class TemplateEngine {
  readonly templateDir: string;
  readonly defaultTemplate: string;
  readonly defaultLayout: string;

  private templates: Map<string, CompiledTemplate> = new Map();
  private layouts: Map<string, CompiledTemplate> = new Map();
  private partialNames: string[] = [];
  private loaded = false;

  constructor(options: TemplateEngineOptions) {
    this.templateDir = path.resolve(options.templateDir);
    this.defaultTemplate = options.defaultTemplate || 'default';
    this.defaultLayout = options.defaultLayout || 'default';
  }

  load(): void {
    if (this.loaded) {
      return;
    }
    loadTemplatesFromDirectory(this.templateDir, this.templates);
    this.loadLayouts();
    this.loadPartials();
    this.loaded = true;
  }

  getTemplateNames(): string[] {
    this.load();
    return [...this.templates.keys()].sort();
  }

  getLayoutNames(): string[] {
    this.load();
    return [...this.layouts.keys()].sort();
  }

  getPartialNames(): string[] {
    this.load();
    return [...this.partialNames].sort();
  }

  hasTemplate(name: string): boolean {
    this.load();
    return this.templates.has(name);
  }

  hasLayout(name: string): boolean {
    this.load();
    return this.layouts.has(name);
  }

  hasContent(): boolean {
    this.load();
    return this.templates.size > 0 || this.layouts.size > 0;
  }

  renderTemplate(name: string, context: PageContext = {}): string {
    this.load();
    const template = this.templates.get(name);
    if (!template) {
      throw new Error(
        `Template not found: "${name}" (looked for ${path.join(this.templateDir, `${name}.hbs`)})`
      );
    }
    return template.render(context);
  }

  renderLayout(name: string, context: PageContext = {}): string {
    this.load();
    const layout = this.layouts.get(name);
    if (!layout) {
      throw new Error(
        `Layout not found: "${name}" (looked for ${path.join(this.templateDir, 'layouts', `${name}.hbs`)})`
      );
    }
    return layout.render(context);
  }

  /**
   * Render a page through its template and layout. The template produces the
   * page body which is then injected into the layout's `{{{body}}}` placeholder.
   */
  renderPage(page: Page): string {
    this.load();

    const templateName = resolveName(stringValue(page.template), this.defaultTemplate);
    const layoutName = resolveName(stringValue(page.layout), this.defaultLayout);
    const context = buildPageContext(page);
    const template = this.templates.get(templateName);
    const layout = this.layouts.get(layoutName);

    if (page.template && !template) {
      throw new Error(
        `Template not found: "${templateName}" (looked for ${path.join(this.templateDir, `${templateName}.hbs`)})`
      );
    }
    if (page.layout && !layout) {
      throw new Error(
        `Layout not found: "${layoutName}" (looked for ${path.join(this.templateDir, 'layouts', `${layoutName}.hbs`)})`
      );
    }

    if (!template && !layout) {
      return renderBuiltInPage(page);
    }

    const body = template ? template.render(context) : renderDefaultBody(page);
    return layout ? layout.render({ ...context, body }) : body;
  }

  /**
   * Render the site index. Uses the `index` page template when one exists,
   * otherwise falls back to a plain list of links.
   */
  renderIndex(pages: Page[]): string {
    this.load();
    const context: PageContext = {
      title: 'Index',
      pages: pages.map((page) => ({
        slug: page.slug,
        title: page.title,
        date: page.date,
        tags: page.tags,
      })),
    };
    const layoutName = resolveName(undefined, this.defaultLayout);
    const layout = this.layouts.get(layoutName);
    let body: string;
    const indexTemplate = this.templates.get('index');
    if (indexTemplate) {
      body = indexTemplate.render(context);
    } else {
      body = [
        '<h1>Index</h1>',
        '<ul>',
        ...pages.map((page) => {
          const date = page.date ? ` <span class="date">${escapeHtml(page.date)}</span>` : '';
          return `  <li><a href="${escapeHtml(page.slug)}.html">${escapeHtml(page.title)}</a>${date}</li>`;
        }),
        '</ul>',
      ].join('\n');
    }
    return layout ? layout.render({ ...context, body }) : body;
  }

  private loadLayouts(): void {
    loadTemplatesFromDirectory(path.join(this.templateDir, 'layouts'), this.layouts);
  }

  private loadPartials(): void {
    const dir = path.join(this.templateDir, 'partials');
    if (!fs.existsSync(dir) || !fs.statSync(dir).isDirectory()) {
      return;
    }
    for (const entry of fs.readdirSync(dir).sort()) {
      if (!HBS_EXTENSION.test(entry)) {
        continue;
      }
      const filePath = path.join(dir, entry);
      if (!fs.statSync(filePath).isFile()) {
        continue;
      }
      const name = entry.replace(HBS_EXTENSION, '');
      const source = fs.readFileSync(filePath, 'utf8');
      Handlebars.registerPartial(name, source);
      this.partialNames.push(name);
    }
  }
}
