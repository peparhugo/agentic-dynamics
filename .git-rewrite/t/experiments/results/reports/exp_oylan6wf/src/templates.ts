import Handlebars from 'handlebars';
import { promises as fs } from 'node:fs';
import path from 'node:path';

/**
 * Template engine backed by Handlebars.
 *
 * Expected template directory shape:
 *   templates/
 *     layouts/     default.hbs, post.hbs, ...   (must render {{{content}}})
 *     partials/    header.hbs, footer.hbs, ...  (usable as {{> header}})
 *     page.hbs ... top-level templates addressable by name
 */
export class TemplateEngine {
  private hbs = Handlebars.create();
  private templates = new Map<string, Handlebars.TemplateDelegate>();
  private layouts = new Map<string, Handlebars.TemplateDelegate>();

  constructor() {
    this.registerBuiltinHelpers();
  }

  private registerBuiltinHelpers(): void {
    this.hbs.registerHelper('formatDate', (date: unknown, fmt?: unknown) => {
      if (!(date instanceof Date) || isNaN(date.getTime())) return '';
      if (fmt === 'iso') return date.toISOString();
      return date.toISOString().slice(0, 10); // YYYY-MM-DD
    });
    this.hbs.registerHelper('eq', (a: unknown, b: unknown) => a === b);
    this.hbs.registerHelper('join', (arr: unknown, sep: unknown) =>
      Array.isArray(arr) ? arr.join(typeof sep === 'string' ? sep : ', ') : '',
    );
  }

  registerHelper(name: string, fn: Handlebars.HelperDelegate): void {
    this.hbs.registerHelper(name, fn);
  }

  /** Compile a top-level template from a string (useful for tests). */
  addTemplate(name: string, source: string): void {
    this.templates.set(name, this.hbs.compile(source));
  }

  addLayout(name: string, source: string): void {
    this.layouts.set(name, this.hbs.compile(source));
  }

  addPartial(name: string, source: string): void {
    this.hbs.registerPartial(name, source);
  }

  hasTemplate(name: string): boolean {
    return this.templates.has(name);
  }

  hasLayout(name: string): boolean {
    return this.layouts.has(name);
  }

  /** Load templates, layouts and partials from a directory on disk. */
  async loadDirectory(templateDir: string): Promise<void> {
    const entries = await fs.readdir(templateDir, { withFileTypes: true });
    for (const entry of entries) {
      const full = path.join(templateDir, entry.name);
      if (entry.isDirectory() && entry.name === 'partials') {
        for (const f of await listHbs(full)) {
          this.addPartial(stem(f), await fs.readFile(path.join(full, f), 'utf8'));
        }
      } else if (entry.isDirectory() && entry.name === 'layouts') {
        for (const f of await listHbs(full)) {
          this.addLayout(stem(f), await fs.readFile(path.join(full, f), 'utf8'));
        }
      } else if (entry.isFile() && isHbs(entry.name)) {
        this.addTemplate(stem(entry.name), await fs.readFile(full, 'utf8'));
      }
    }
  }

  /** Render a named top-level template with the given context. */
  renderTemplate(name: string, context: Record<string, unknown>): string {
    const tpl = this.templates.get(name);
    if (!tpl) throw new Error(`Template not found: "${name}"`);
    return tpl(context);
  }

  /**
   * Render a page: run `templateName` (or use `content` directly if no
   * template given), then wrap the result in `layoutName` where the layout
   * receives the rendered body as {{{content}}}.
   */
  renderPage(opts: {
    layout?: string;
    template?: string;
    content?: string;
    context: Record<string, unknown>;
  }): string {
    const { layout = 'default', template, content = '', context } = opts;
    const inner = template ? this.renderTemplate(template, context) : content;
    const layoutTpl = this.layouts.get(layout);
    if (!layoutTpl) {
      if (layout === 'default') return inner; // no default layout: passthrough
      throw new Error(`Layout not found: "${layout}"`);
    }
    return layoutTpl({ ...context, content: inner });
  }
}

const isHbs = (f: string) => /\.(hbs|handlebars|html)$/.test(f);
const stem = (f: string) => f.replace(/\.(hbs|handlebars|html)$/, '');
async function listHbs(dir: string): Promise<string[]> {
  return (await fs.readdir(dir)).filter(isHbs);
}
