import { existsSync, readdirSync, readFileSync } from 'fs';
import { basename, extname, join } from 'path';
import Handlebars from 'handlebars';
import ejs from 'ejs';
import { Page } from './page';
import { dateElement, tagSpans } from './html';
import { pageHtml, indexHtml } from './templates';

export type TemplateKind = 'hbs' | 'ejs';

export interface TemplateSource {
  name: string;
  kind: TemplateKind;
  source: string;
  filePath: string;
}

export interface PageContext {
  slug: string;
  title: string;
  date: string;
  tags: string[];
  content: string;
  meta: string;
  hasMeta: boolean;
  [key: string]: unknown;
}

export interface IndexItemContext {
  slug: string;
  title: string;
  date: string;
  tags: string[];
  meta: string;
}

export interface IndexContext {
  title: string;
  pages: IndexItemContext[];
  [key: string]: unknown;
}

const TEMPLATE_EXTENSIONS: Record<TemplateKind, string> = { hbs: '.hbs', ejs: '.ejs' };

function templateKindFor(filePath: string): TemplateKind | null {
  const ext = extname(filePath);
  if (ext === TEMPLATE_EXTENSIONS.hbs) return 'hbs';
  if (ext === TEMPLATE_EXTENSIONS.ejs) return 'ejs';
  return null;
}

function loadSources(dir: string): TemplateSource[] {
  if (!existsSync(dir)) return [];
  const sources: TemplateSource[] = [];
  const entries = readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    if (!entry.isFile()) continue;
    const filePath = join(dir, entry.name);
    const kind = templateKindFor(entry.name);
    if (kind === null) continue;
    const name = basename(entry.name, extname(entry.name));
    sources.push({ name, kind, source: readFileSync(filePath, 'utf8'), filePath });
  }
  return sources;
}

function pageContext(page: Page): PageContext {
  const meta = [dateElement(page.date), tagSpans(page.tags)]
    .filter((part) => part.length > 0)
    .join(' ');
  return {
    slug: page.slug,
    title: page.title,
    date: page.date,
    tags: page.tags,
    content: page.contentHtml,
    meta,
    hasMeta: meta.length > 0,
  };
}

export class TemplateEngine {
  private pageTemplates: TemplateSource[] = [];
  private layouts: TemplateSource[] = [];
  private partials: TemplateSource[] = [];
  private defaultTemplateName: string | undefined;
  private defaultLayoutName: string | undefined;
  private indexTemplateName: string | undefined;
  private hbsPartialsRegistered = false;
  private hbs: typeof Handlebars;
  private hbsCache = new Map<string, Handlebars.TemplateDelegate>();

  constructor(private templatesDir: string) {
    this.hbs = Handlebars.create();
  }

  load(): boolean {
    this.pageTemplates = loadSources(this.templatesDir);
    this.layouts = loadSources(join(this.templatesDir, 'layouts'));
    this.partials = loadSources(join(this.templatesDir, 'partials'));

    this.defaultTemplateName = this.pickDefault(this.pageTemplates);
    this.defaultLayoutName = this.pickDefault(this.layouts);
    const indexTemplate = this.findByName(this.pageTemplates, 'index');
    this.indexTemplateName = indexTemplate ? indexTemplate.name : undefined;

    return this.pageTemplates.length > 0 || this.layouts.length > 0;
  }

  private findByName(sources: TemplateSource[], name: string): TemplateSource | undefined {
    return sources.find((source) => source.name === name);
  }

  private pickDefault(sources: TemplateSource[]): string | undefined {
    const named = this.findByName(sources, 'default');
    if (named) return named.name;
    if (sources.length > 0) return sources[0].name;
    return undefined;
  }

  private registerHandlebarsPartials(): void {
    if (this.hbsPartialsRegistered) return;
    for (const partial of this.partials) {
      if (partial.kind === 'hbs') {
        this.hbs.registerPartial(partial.name, partial.source);
      }
    }
    this.hbsPartialsRegistered = true;
  }

  private renderSource(source: TemplateSource, context: Record<string, unknown>): string {
    if (source.kind === 'hbs') {
      this.registerHandlebarsPartials();
      const key = source.filePath;
      let compiled = this.hbsCache.get(key);
      if (!compiled) {
        compiled = this.hbs.compile(source.source);
        this.hbsCache.set(key, compiled);
      }
      return compiled(context);
    }
    return ejs.render(source.source, context, { filename: source.filePath });
  }

  private renderLayout(layout: TemplateSource, body: string, context: Record<string, unknown>): string {
    return this.renderSource(layout, { ...context, body });
  }

  hasPageTemplate(name: string): boolean {
    return this.findByName(this.pageTemplates, name) !== undefined;
  }

  hasLayout(name: string): boolean {
    return this.findByName(this.layouts, name) !== undefined;
  }

  renderPage(page: Page): string {
    const templateName = page.template ?? this.defaultTemplateName;
    const template = templateName ? this.findByName(this.pageTemplates, templateName) : undefined;

    const context = pageContext(page);
    const body = template ? this.renderSource(template, context) : context.content;

    const layoutName = page.layout ?? this.defaultLayoutName;
    const layout = layoutName ? this.findByName(this.layouts, layoutName) : undefined;
    if (layout) {
      return this.renderLayout(layout, body, context);
    }
    if (template) {
      return body;
    }
    return pageHtml(page);
  }

  renderIndex(pages: Page[]): string {
    const indexTemplate = this.indexTemplateName ? this.findByName(this.pageTemplates, this.indexTemplateName) : undefined;
    const items: IndexItemContext[] = pages.map((page) => {
      const context = pageContext(page);
      return {
        slug: page.slug,
        title: page.title,
        date: page.date,
        tags: page.tags,
        meta: context.meta,
      };
    });

    const indexContext: IndexContext = { title: 'Home', pages: items };
    if (!indexTemplate) {
      return indexHtml(pages);
    }

    const body = this.renderSource(indexTemplate, indexContext);
    const layout = this.defaultLayoutName ? this.findByName(this.layouts, this.defaultLayoutName) : undefined;
    if (layout) {
      return this.renderLayout(layout, body, indexContext);
    }
    return body;
  }
}

export function loadTemplates(templatesDir: string): TemplateEngine | null {
  const engine = new TemplateEngine(templatesDir);
  if (!engine.load()) return null;
  return engine;
}
