import fs from 'fs';
import path from 'path';
import Handlebars from 'handlebars';
import { Page } from './types';
import { escapeHtml } from './parser';

export const DEFAULT_TEMPLATE_NAME = 'default';
export const DEFAULT_LAYOUT_NAME = 'default';

export interface TemplateConfig {
  templateDir: string;
  defaultTemplate?: string;
  defaultLayout?: string;
}

function walk(dir: string): string[] {
  const results: string[] = [];
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  entries.sort((a, b) => a.name.localeCompare(b.name));
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      results.push(...walk(fullPath));
    } else if (entry.isFile() && entry.name.toLowerCase().endsWith('.hbs')) {
      results.push(fullPath);
    }
  }
  return results;
}

function tagsHtml(tags: string[]): string {
  if (tags.length === 0) return '';
  const chips = tags.map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`).join('');
  return `<div class="tags">${chips}</div>`;
}

export function builtInArticle(page: Page): string {
  const title = escapeHtml(page.title);
  const date = page.date ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '';
  return `    <article>
      <h1>${title}</h1>
      ${date ? `<p class="date">${date}</p>` : ''}
      ${tagsHtml(page.tags)}
      <div class="content">
${page.html}
      </div>
    </article>`;
}

export function builtInPage(page: Page): string {
  const title = escapeHtml(page.title);
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${title}</title>
</head>
<body>
  <header>
    <nav><a href="index.html">Home</a></nav>
  </header>
  <main>
${builtInArticle(page)}
  </main>
</body>
</html>
`;
}

function makeContext(page: Page): Record<string, unknown> {
  return {
    page: {
      sourcePath: page.sourcePath,
      slug: page.slug,
      title: page.title,
      date: page.date,
      tags: page.tags,
      content: page.content,
      html: page.html,
    },
    title: page.title,
    date: page.date,
    slug: page.slug,
    tags: page.tags,
    content: page.content,
    html: page.html,
    body: '',
    site: { title: 'Site' },
  };
}

export class TemplateEngine {
  private readonly config: TemplateConfig;
  private readonly templates = new Map<string, Handlebars.TemplateDelegate>();
  private readonly layouts = new Map<string, Handlebars.TemplateDelegate>();
  private readonly partialsRegistered: string[] = [];
  private readonly hasTemplates: boolean;

  constructor(config: TemplateConfig) {
    this.config = config;
    this.hasTemplates = this.load();
  }

  private load(): boolean {
    const dir = this.config.templateDir;
    if (!fs.existsSync(dir)) {
      return false;
    }

    const partialsDir = path.join(dir, 'partials');
    if (fs.existsSync(partialsDir)) {
      for (const file of walk(partialsDir)) {
        const name = path.basename(file, path.extname(file));
        Handlebars.registerPartial(name, fs.readFileSync(file, 'utf8'));
        this.partialsRegistered.push(name);
      }
    }

    const layoutsDir = path.join(dir, 'layouts');
    if (fs.existsSync(layoutsDir)) {
      for (const file of walk(layoutsDir)) {
        const name = path.basename(file, path.extname(file));
        this.layouts.set(name, Handlebars.compile(fs.readFileSync(file, 'utf8')));
      }
    }

    for (const file of walk(dir)) {
      const rel = path.relative(dir, file).replace(/\\/g, '/');
      if (rel.startsWith('partials/') || rel.startsWith('layouts/')) {
        continue;
      }
      const base = path.basename(file, path.extname(file));
      const namespaced = rel.slice(0, -path.extname(file).length);
      const compiled = Handlebars.compile(fs.readFileSync(file, 'utf8'));
      this.templates.set(base, compiled);
      if (namespaced !== base) {
        this.templates.set(namespaced, compiled);
      }
    }

    return this.templates.size > 0 || this.layouts.size > 0 || this.partialsRegistered.length > 0;
  }

  get active(): boolean {
    return this.hasTemplates;
  }

  getPartialNames(): string[] {
    return [...this.partialsRegistered];
  }

  getTemplateNames(): string[] {
    return [...this.templates.keys()];
  }

  getLayoutNames(): string[] {
    return [...this.layouts.keys()];
  }

  private findTemplate(name?: string): Handlebars.TemplateDelegate | undefined {
    if (name) {
      const explicit = this.templates.get(name);
      if (explicit) {
        return explicit;
      }
    }
    const fallback = this.config.defaultTemplate ?? DEFAULT_TEMPLATE_NAME;
    return this.templates.get(fallback);
  }

  private findLayout(name?: string): Handlebars.TemplateDelegate | undefined {
    if (name) {
      const explicit = this.layouts.get(name);
      if (explicit) {
        return explicit;
      }
    }
    const fallback = this.config.defaultLayout ?? DEFAULT_LAYOUT_NAME;
    return this.layouts.get(fallback);
  }

  renderPage(page: Page): string {
    if (!this.active) {
      return builtInPage(page);
    }

    const template = this.findTemplate(page.template);
    const layout = this.findLayout(page.layout);
    if (!template && !layout) {
      return builtInPage(page);
    }

    const context = makeContext(page);
    let body: string;
    if (template) {
      body = template(context);
    } else {
      body = builtInArticle(page);
    }

    if (layout) {
      context.body = body;
      return layout(context);
    }
    return body;
  }

  renderIndex(pages: Page[]): string {
    return renderIndex(pages);
  }
}

export function renderPage(page: Page, engine?: TemplateEngine): string {
  if (engine) {
    return engine.renderPage(page);
  }
  return builtInPage(page);
}

export function renderIndex(pages: Page[]): string {
  const sorted = [...pages].sort((a, b) => {
    if (a.date && b.date) {
      return a.date < b.date ? 1 : a.date > b.date ? -1 : 0;
    }
    return a.title.localeCompare(b.title);
  });

  const items = sorted
    .map((page) => {
      const date = page.date ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time> ` : '';
      return `    <li>
      <a href="${escapeHtml(page.slug)}.html"><h2>${escapeHtml(page.title)}</h2></a>
      ${date ? `<span class="date">${date}</span>` : ''}
      ${tagsHtml(page.tags)}
    </li>`;
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
  <header><h1>Site</h1></header>
  <main>
    <ul class="pages">
${items}
    </ul>
  </main>
</body>
</html>
`;
}
