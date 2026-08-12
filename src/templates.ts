import fs from 'fs';
import path from 'path';
import Handlebars from 'handlebars';
import { Page } from './types';

export interface TemplateContext {
  slug: string;
  content: string;
  html: string;
  title?: string;
  date?: string;
  tags?: string[];
  template?: string;
  layout?: string;
  body?: string;
  pages?: TemplateContext[];
  [key: string]: unknown;
}

type Compiled = Handlebars.TemplateDelegate;

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...walk(full));
    else if (entry.isFile()) out.push(full);
  }
  return out;
}

export class TemplateEngine {
  private hbs = Handlebars.create();
  private templates = new Map<string, Compiled>();
  private layouts = new Map<string, Compiled>();

  constructor(private templatesDir: string) {
    if (!fs.existsSync(templatesDir)) {
      throw new Error(`Templates directory does not exist: ${templatesDir}`);
    }
    this.loadPartials();
    this.loadLayouts();
    this.loadTemplates();
  }

  private loadPartials(): void {
    const dir = path.join(this.templatesDir, 'partials');
    if (!fs.existsSync(dir)) return;
    for (const file of walk(dir)) {
      if (!file.endsWith('.hbs')) continue;
      const rel = path.relative(dir, file);
      const name = rel.slice(0, -'.hbs'.length).split(path.sep).join('/');
      this.hbs.registerPartial(name, fs.readFileSync(file, 'utf-8'));
    }
  }

  private loadLayouts(): void {
    const dir = path.join(this.templatesDir, 'layouts');
    if (!fs.existsSync(dir)) return;
    for (const file of walk(dir)) {
      if (!file.endsWith('.hbs')) continue;
      const name = path.basename(file, '.hbs');
      this.layouts.set(name, this.hbs.compile(fs.readFileSync(file, 'utf-8')));
    }
  }

  private loadTemplates(): void {
    for (const file of walk(this.templatesDir)) {
      if (!file.endsWith('.hbs')) continue;
      const parts = path.relative(this.templatesDir, file).split(path.sep);
      if (parts[0] === 'layouts' || parts[0] === 'partials') continue;
      const name = path.basename(file, '.hbs');
      this.templates.set(name, this.hbs.compile(fs.readFileSync(file, 'utf-8')));
    }
  }

  private static toContext(page: Page): TemplateContext {
    return { slug: page.slug, content: page.content, html: page.html, ...page.data };
  }

  private wrap(context: TemplateContext, body: string): string {
    const layoutName =
      typeof context.layout === 'string' && context.layout ? context.layout : 'base';
    const layout = this.layouts.get(layoutName);
    return layout ? layout({ ...context, body }) : body;
  }

  renderPage(page: Page): string | undefined {
    const context = TemplateEngine.toContext(page);
    const templateName =
      typeof context.template === 'string' && context.template ? context.template : 'default';
    const tpl = this.templates.get(templateName) ?? this.templates.get('default');
    if (!tpl) return undefined;
    return this.wrap(context, tpl(context));
  }

  renderIndex(pages: Page[]): string | undefined {
    const tpl = this.templates.get('index') ?? this.templates.get('default');
    if (!tpl) return undefined;
    const context: TemplateContext = {
      slug: 'index',
      content: '',
      html: '',
      title: 'Home',
      pages: pages.map(TemplateEngine.toContext),
    };
    return this.wrap(context, tpl(context));
  }
}

export function createTemplateEngine(templatesDir: string): TemplateEngine {
  return new TemplateEngine(templatesDir);
}
