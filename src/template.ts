import fs from 'fs';
import path from 'path';
import Handlebars from 'handlebars';
import ejs from 'ejs';
import { Page } from './types';

export const DEFAULT_TEMPLATES_DIR = './templates';
export const DEFAULT_PAGE_TEMPLATE_NAME = 'default';
export const DEFAULT_LAYOUT_NAME = 'default';

const TEMPLATE_RE = /\.(hbs|ejs)$/i;

export interface TemplateContext {
  page: Record<string, unknown>;
  title: string;
  date?: string;
  tags: string[];
  content: string;
  body?: string;
  pages?: Page[];
  site?: Record<string, unknown>;
  [key: string]: unknown;
}

interface TemplateSource {
  source: string;
  ext: string;
}

function listTemplateFiles(dir: string): string[] {
  if (!fs.existsSync(dir)) {
    return [];
  }
  return fs
    .readdirSync(dir, { withFileTypes: true })
    .filter((entry) => entry.isFile() && TEMPLATE_RE.test(entry.name))
    .map((entry) => path.join(dir, entry.name))
    .sort();
}

function nameWithoutExt(filePath: string): string {
  const base = path.basename(filePath);
  return base.replace(/\.(hbs|ejs)$/i, '');
}

export function pageToContext(page: Page, body?: string): TemplateContext {
  const pageData: Record<string, unknown> = {
    ...(page.data ?? {}),
    slug: page.slug,
    title: page.title,
    date: page.date,
    tags: page.tags,
    content: page.content,
    template: page.template,
    layout: page.layout,
  };
  return {
    page: pageData,
    title: page.title,
    date: page.date,
    tags: page.tags,
    content: page.content,
    body,
  };
}

export class TemplateEngine {
  readonly templatesDir: string;
  readonly enabled: boolean;

  private pageTemplates = new Map<string, TemplateSource>();
  private layouts = new Map<string, TemplateSource>();
  private indexTemplate?: TemplateSource;

  constructor(templatesDir: string) {
    this.templatesDir = path.resolve(templatesDir);
    this.enabled = fs.existsSync(this.templatesDir);
    if (this.enabled) {
      this.load();
    }
  }

  private load(): void {
    const partialsDir = path.join(this.templatesDir, 'partials');
    for (const file of listTemplateFiles(partialsDir)) {
      const source = fs.readFileSync(file, 'utf8');
      Handlebars.registerPartial(nameWithoutExt(file), source);
    }

    const layoutsDir = path.join(this.templatesDir, 'layouts');
    for (const file of listTemplateFiles(layoutsDir)) {
      this.layouts.set(nameWithoutExt(file), {
        source: fs.readFileSync(file, 'utf8'),
        ext: path.extname(file),
      });
    }

    for (const file of listTemplateFiles(this.templatesDir)) {
      const name = nameWithoutExt(file);
      if (name === 'index') {
        this.indexTemplate = {
          source: fs.readFileSync(file, 'utf8'),
          ext: path.extname(file),
        };
      } else {
        this.pageTemplates.set(name, {
          source: fs.readFileSync(file, 'utf8'),
          ext: path.extname(file),
        });
      }
    }
  }

  hasTemplate(name: string): boolean {
    return this.pageTemplates.has(name);
  }

  hasLayout(name: string): boolean {
    return this.layouts.has(name);
  }

  getPageTemplate(name: string): TemplateSource | undefined {
    return this.pageTemplates.get(name);
  }

  getLayout(name: string): TemplateSource | undefined {
    return this.layouts.get(name);
  }

  getIndexTemplate(): TemplateSource | undefined {
    return this.indexTemplate;
  }

  render(source: string, ext: string, context: TemplateContext): string {
    if (ext.toLowerCase() === '.ejs') {
      return ejs.render(source, context, {
        filename: path.join(this.templatesDir, 'layout.ejs'),
        root: this.templatesDir,
        views: [this.templatesDir],
      });
    }
    return Handlebars.compile(source)(context);
  }
}

export function renderTemplateFile(
  templatesDir: string,
  relativePath: string,
  context: TemplateContext,
): string {
  const full = path.resolve(templatesDir, relativePath);
  const ext = path.extname(full);
  return new TemplateEngine(templatesDir).render(
    fs.readFileSync(full, 'utf8'),
    ext,
    context,
  );
}
