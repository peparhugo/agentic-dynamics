import fs from 'fs';
import path from 'path';
import Handlebars from 'handlebars';
import matter from 'gray-matter';
import type { Page, PageData } from './types';
import { pageTitle } from './generator';

export const DEFAULT_TEMPLATE_NAME = 'default';
export const DEFAULT_LAYOUT_NAME = 'default';
export const LAYOUT_DIR = 'layouts';
export const PARTIALS_DIR = 'partials';

export interface TemplateMeta {
  layout?: string;
}

export interface SitePageRef {
  slug: string;
  title: string;
  outputFile: string;
  date?: string;
}

export interface SiteContext {
  pages: SitePageRef[];
}

/**
 * A Handlebars-based template engine for the static site generator.
 *
 * Directory layout:
 *   <templatesDir>/              page templates (<name>.hbs)
 *   <templatesDir>/layouts/      layout templates (<name>.hbs) using {{{body}}}
 *   <templatesDir>/partials/     reusable partials registered by file name
 *
 * Pages opt in via frontmatter:
 *   template: post    -> templates/post.hbs (defaults to templates/default.hbs)
 *   layout: base      -> templates/layouts/base.hbs (defaults to 'default')
 */
export class TemplateEngine {
  private readonly cache = new Map<string, string>();

  constructor(readonly templatesDir: string) {
    if (!fs.existsSync(this.templatesDir)) {
      throw new Error(`templates directory not found: ${this.templatesDir}`);
    }
    this.registerPartials();
  }

  private readCached(file: string): string {
    if (!this.cache.has(file)) {
      this.cache.set(file, fs.readFileSync(file, 'utf-8'));
    }
    return this.cache.get(file)!;
  }

  private registerPartials(): void {
    const dir = path.join(this.templatesDir, PARTIALS_DIR);
    if (!fs.existsSync(dir)) {
      return;
    }
    for (const file of fs.readdirSync(dir)) {
      if (!file.toLowerCase().endsWith('.hbs')) continue;
      const name = path.basename(file, path.extname(file));
      const source = this.readCached(path.join(dir, file));
      Handlebars.registerPartial(name, source);
    }
  }

  private templateSource(name: string): string | null {
    const file = path.join(this.templatesDir, `${name}.hbs`);
    return fs.existsSync(file) ? this.readCached(file) : null;
  }

  private layoutSource(name: string): string | null {
    const file = path.join(this.templatesDir, LAYOUT_DIR, `${name}.hbs`);
    return fs.existsSync(file) ? this.readCached(file) : null;
  }

  hasTemplate(name: string): boolean {
    return this.templateSource(name) !== null;
  }

  hasLayout(name: string): boolean {
    return this.layoutSource(name) !== null;
  }

  private parseMeta(source: string): TemplateMeta {
    const parsed = matter(source);
    const data = parsed && typeof parsed.data === 'object' ? (parsed.data as PageData) : {};
    const layout = data.layout !== undefined ? String(data.layout) : undefined;
    return { layout };
  }

  render(source: string, context: Record<string, unknown>): string {
    return Handlebars.compile(source)(context);
  }

  pageContext(page: Page, site?: SiteContext): Record<string, unknown> {
    const context: Record<string, unknown> = {
      ...page.data,
      title: pageTitle(page.data, page.slug),
      body: page.html,
      slug: page.slug,
      sourcePath: page.sourcePath,
      outputFile: page.outputFile,
      page: { ...page, data: page.data },
    };
    if (site) {
      context.site = site;
    }
    return context;
  }

  resolveTemplateName(page: Page): string | null {
    const requested =
      page.data.template !== undefined ? String(page.data.template) : DEFAULT_TEMPLATE_NAME;
    if (this.templateSource(requested) !== null) {
      return requested;
    }
    if (requested !== DEFAULT_TEMPLATE_NAME && this.templateSource(DEFAULT_TEMPLATE_NAME) !== null) {
      return DEFAULT_TEMPLATE_NAME;
    }
    return null;
  }

  renderPage(page: Page, site?: SiteContext): string | null {
    const templateName = this.resolveTemplateName(page);
    if (templateName === null) {
      return null;
    }

    const templateSource = this.templateSource(templateName)!;
    const templateMeta = this.parseMeta(templateSource);
    const context = this.pageContext(page, site);

    const content = this.render(templateSource, context);

    const layoutName =
      page.data.layout !== undefined
        ? String(page.data.layout)
        : templateMeta.layout || DEFAULT_LAYOUT_NAME;

    let layoutSource = this.layoutSource(layoutName);
    if (layoutSource === null && layoutName !== DEFAULT_LAYOUT_NAME) {
      layoutSource = this.layoutSource(DEFAULT_LAYOUT_NAME);
    }
    if (layoutSource === null) {
      return content;
    }

    return this.render(layoutSource, { ...context, body: content });
  }
}
