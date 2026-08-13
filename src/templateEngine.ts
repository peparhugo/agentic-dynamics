import * as fs from 'fs';
import * as path from 'path';
import Handlebars from 'handlebars';
import { renderArticleBody, renderIndexBody } from './templates';
import { Page } from './types';

const DEFAULT_LAYOUT_NAME = 'default';
const PARTIAL_NAMES = ['header', 'nav', 'footer'];

/**
 * Loads Handlebars layouts (templates/layouts/*.hbs) and partials
 * (templates/partials/*.hbs) from a templates directory and renders pages
 * through them. `header`/`nav`/`footer` partials default to empty strings
 * so a layout can reference them via `{{> header}}` even if the project
 * hasn't created that partial file yet.
 */
export class TemplateEngine {
  private readonly hb: typeof Handlebars;
  private readonly templatesDir: string;
  private readonly layoutCache = new Map<string, Handlebars.TemplateDelegate | undefined>();

  constructor(templatesDir: string) {
    this.templatesDir = templatesDir;
    this.hb = Handlebars.create();
    for (const name of PARTIAL_NAMES) {
      this.hb.registerPartial(name, '');
    }
    this.loadPartials();
  }

  private loadPartials(): void {
    const partialsDir = path.join(this.templatesDir, 'partials');
    if (!fs.existsSync(partialsDir)) return;

    for (const file of fs.readdirSync(partialsDir)) {
      if (path.extname(file) !== '.hbs') continue;
      const name = path.basename(file, '.hbs');
      const source = fs.readFileSync(path.join(partialsDir, file), 'utf-8');
      this.hb.registerPartial(name, source);
    }
  }

  private getLayout(name: string): Handlebars.TemplateDelegate | undefined {
    if (this.layoutCache.has(name)) {
      return this.layoutCache.get(name);
    }

    const layoutPath = path.join(this.templatesDir, 'layouts', `${name}.hbs`);
    let compiled: Handlebars.TemplateDelegate | undefined;
    if (fs.existsSync(layoutPath)) {
      const source = fs.readFileSync(layoutPath, 'utf-8');
      compiled = this.hb.compile(source);
    }

    this.layoutCache.set(name, compiled);
    return compiled;
  }

  /**
   * Renders a page through its requested layout (frontmatter `template`,
   * falling back to "default"). Returns undefined when neither layout
   * exists, so the caller can fall back to the built-in renderer.
   */
  renderPage(page: Page, pages: Page[]): string | undefined {
    const requested = page.template || DEFAULT_LAYOUT_NAME;
    const layout = this.getLayout(requested) ?? this.getLayout(DEFAULT_LAYOUT_NAME);
    if (!layout) return undefined;

    return layout({
      page,
      pages,
      body: renderArticleBody(page),
      title: page.title,
      date: page.date,
      tags: page.tags,
    });
  }

  /**
   * Renders the home/index page through the "index" layout, falling back
   * to "default". Returns undefined when neither exists.
   */
  renderIndex(pages: Page[]): string | undefined {
    const layout = this.getLayout('index') ?? this.getLayout(DEFAULT_LAYOUT_NAME);
    if (!layout) return undefined;

    return layout({
      pages,
      body: renderIndexBody(pages),
      title: 'Home',
    });
  }
}
