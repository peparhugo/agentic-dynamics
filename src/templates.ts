import Handlebars from 'handlebars';
import { readdir, readFile } from 'node:fs/promises';
import path from 'node:path';
import type { Page } from './types';

export const DEFAULT_TEMPLATE_NAME = 'default';
export const DEFAULT_LAYOUT_NAME = 'default';
export const DEFAULT_TEMPLATE_DIR = 'templates';

export const LAYOUTS_DIR = 'layouts';
export const PARTIALS_DIR = 'partials';

const TEMPLATE_EXTENSION = /\.(hbs|handlebars)$/i;

export interface TemplateContext {
  title: string;
  date: string;
  tags: string[];
  slug: string;
  source: string;
  body: string;
  [key: string]: unknown;
}

type CompiledTemplate = Handlebars.TemplateDelegate;

export class TemplateEngine {
  readonly templatesDir: string;

  private readonly templates = new Map<string, string>();
  private readonly layouts = new Map<string, string>();
  private readonly compiledTemplates = new Map<string, CompiledTemplate>();
  private readonly compiledLayouts = new Map<string, CompiledTemplate>();

  constructor(templatesDir: string) {
    this.templatesDir = templatesDir;
  }

  async load(): Promise<void> {
    await this.loadDirectory(this.templatesDir, this.templates);
    await this.loadDirectory(path.join(this.templatesDir, LAYOUTS_DIR), this.layouts);
    await this.loadPartials(path.join(this.templatesDir, PARTIALS_DIR));
  }

  hasTemplates(): boolean {
    return this.templates.size > 0;
  }

  hasTemplate(name: string): boolean {
    return this.templates.has(name);
  }

  hasLayout(name: string): boolean {
    return this.layouts.has(name);
  }

  renderTemplate(name: string, context: TemplateContext): string {
    const source = this.templates.get(name);
    if (source === undefined) {
      throw new Error(`Template not found: ${name}`);
    }
    const compiled = this.compile(this.templates, this.compiledTemplates, name, source);
    return compiled(context);
  }

  renderLayout(name: string, context: TemplateContext): string {
    const source = this.layouts.get(name);
    if (source === undefined) {
      throw new Error(`Layout not found: ${name}`);
    }
    const compiled = this.compile(this.layouts, this.compiledLayouts, name, source);
    return compiled(context);
  }

  renderPage(page: Page, body: string): string {
    const templateName = page.template || DEFAULT_TEMPLATE_NAME;
    if (!this.templates.has(templateName)) {
      throw new Error(`Template not found: ${templateName}`);
    }

    const context = buildContext(page, body);
    const content = this.renderTemplate(templateName, context);

    const layoutName = page.layout || DEFAULT_LAYOUT_NAME;
    if (page.layout && !this.layouts.has(layoutName)) {
      throw new Error(`Layout not found: ${layoutName}`);
    }
    if (this.layouts.has(layoutName)) {
      return this.renderLayout(layoutName, { ...context, body: content });
    }
    return content;
  }

  private async loadDirectory(dir: string, target: Map<string, string>): Promise<void> {
    let entries;
    try {
      entries = await readdir(dir, { withFileTypes: true });
    } catch {
      return;
    }
    for (const entry of entries) {
      if (entry.isFile() && TEMPLATE_EXTENSION.test(entry.name)) {
        const full = path.join(dir, entry.name);
        target.set(path.parse(entry.name).name, await readFile(full, 'utf8'));
      }
    }
  }

  private async loadPartials(dir: string): Promise<void> {
    let entries;
    try {
      entries = await readdir(dir, { withFileTypes: true });
    } catch {
      return;
    }
    for (const entry of entries) {
      if (entry.isFile() && TEMPLATE_EXTENSION.test(entry.name)) {
        const full = path.join(dir, entry.name);
        Handlebars.registerPartial(path.parse(entry.name).name, await readFile(full, 'utf8'));
      }
    }
  }

  private compile(
    sources: Map<string, string>,
    cache: Map<string, CompiledTemplate>,
    name: string,
    source: string,
  ): CompiledTemplate {
    let compiled = cache.get(name);
    if (!compiled) {
      compiled = Handlebars.compile(source);
      cache.set(name, compiled);
    }
    return compiled;
  }
}

export function buildContext(page: Page, body: string): TemplateContext {
  const context: TemplateContext = {
    title: page.title,
    date: page.date,
    tags: page.tags,
    slug: page.slug,
    source: page.source,
    body,
  };
  if (page.data) {
    for (const [key, value] of Object.entries(page.data)) {
      context[key] = value;
    }
  }
  return context;
}
