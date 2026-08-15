import Handlebars from 'handlebars';
import { promises as fs } from 'fs';
import type { Dirent } from 'fs';
import path from 'path';

export type TemplateContext = Record<string, unknown>;

const EXTENSIONS = ['.hbs', '.handlebars', '.html'];
const PARTIAL_EXTENSIONS = ['.hbs', '.handlebars'];

const DEFAULT_PAGE_TEMPLATE = `  <article>
    <h1>{{title}}</h1>
    {{#if meta}}<p class="meta">{{{meta}}}</p>{{/if}}
    {{{contentHtml}}}
  </article>
`;

const DEFAULT_LAYOUT = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{title}}</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 48rem; margin: 0 auto; padding: 2rem 1rem; line-height: 1.6; }
    a { color: #2563eb; }
    .tags span { background: #e5e7eb; border-radius: 9999px; padding: 0.15rem 0.6rem; font-size: 0.8rem; margin-right: 0.35rem; }
    .meta { color: #6b7280; font-size: 0.9rem; }
  </style>
</head>
<body>
  <p><a href="index.html">&larr; All pages</a></p>
{{{body}}}
</body>
</html>
`;

function stripExtension(name: string): string {
  for (const ext of EXTENSIONS) {
    if (name.endsWith(ext)) {
      return name.slice(0, -ext.length);
    }
  }
  return name;
}

async function readEntries(dir: string): Promise<Dirent[]> {
  try {
    return await fs.readdir(dir, { withFileTypes: true });
  } catch {
    return [];
  }
}

export class TemplateEngine {
  private readonly root: string;
  private readonly hbs: typeof Handlebars;
  private readonly pageTemplates = new Map<string, Handlebars.TemplateDelegate>();
  private readonly layouts = new Map<string, Handlebars.TemplateDelegate>();
  private readonly defaultPageTemplate: Handlebars.TemplateDelegate;
  private readonly defaultLayout: Handlebars.TemplateDelegate;

  constructor(root: string) {
    this.root = path.resolve(root);
    this.hbs = Handlebars.create();
    this.defaultPageTemplate = this.hbs.compile(DEFAULT_PAGE_TEMPLATE);
    this.defaultLayout = this.hbs.compile(DEFAULT_LAYOUT);
  }

  async load(): Promise<void> {
    await this.loadPartials();
    await this.loadLayouts();
    await this.loadPageTemplates();
  }

  private async loadPartials(): Promise<void> {
    const dir = path.join(this.root, 'partials');
    for (const entry of await readEntries(dir)) {
      if (!entry.isFile()) {
        continue;
      }
      const ext = path.extname(entry.name);
      if (!PARTIAL_EXTENSIONS.includes(ext)) {
        continue;
      }
      const name = entry.name.slice(0, -ext.length);
      const source = await fs.readFile(path.join(dir, entry.name), 'utf8');
      this.hbs.registerPartial(name, this.hbs.compile(source));
    }
  }

  private async loadLayouts(): Promise<void> {
    const dir = path.join(this.root, 'layouts');
    for (const entry of await readEntries(dir)) {
      if (!entry.isFile()) {
        continue;
      }
      const ext = path.extname(entry.name);
      if (!EXTENSIONS.includes(ext)) {
        continue;
      }
      const name = entry.name.slice(0, -ext.length);
      const source = await fs.readFile(path.join(dir, entry.name), 'utf8');
      this.layouts.set(name, this.hbs.compile(source));
    }
  }

  private async loadPageTemplates(): Promise<void> {
    for (const entry of await readEntries(this.root)) {
      if (!entry.isFile()) {
        continue;
      }
      const ext = path.extname(entry.name);
      if (!EXTENSIONS.includes(ext)) {
        continue;
      }
      const name = entry.name.slice(0, -ext.length);
      const source = await fs.readFile(path.join(this.root, entry.name), 'utf8');
      this.pageTemplates.set(name, this.hbs.compile(source));
    }
  }

  render(name: string, context: TemplateContext): string {
    const template = this.pageTemplates.get(stripExtension(name));
    if (template) {
      return template(context);
    }
    return this.defaultPageTemplate(context);
  }

  renderLayout(name: string, context: TemplateContext): string {
    const layout = this.layouts.get(stripExtension(name));
    if (layout) {
      return layout(context);
    }
    return this.defaultLayout(context);
  }
}
