import fs from 'fs';
import path from 'path';
import Handlebars from 'handlebars';
import { Page } from './types';

export class Renderer {
  private templates: Map<string, HandlebarsTemplateDelegate> = new Map();
  private templateDir: string;

  constructor(templateDir: string) {
    this.templateDir = templateDir;
    this.loadTemplates();
    this.loadPartials();
  }

  private loadTemplates(): void {
    const loadDir = (dir: string) => {
      if (!fs.existsSync(dir)) return;
      const entries = fs.readdirSync(dir, { withFileTypes: true });
      for (const entry of entries) {
        const fullPath = path.join(dir, entry.name);
        if (entry.isDirectory()) {
          continue;
        }
        if (entry.name.endsWith('.hbs')) {
          const name = entry.name.replace(/\.hbs$/, '');
          const template = fs.readFileSync(fullPath, 'utf-8');
          this.templates.set(name, Handlebars.compile(template));
        }
      }
    };

    loadDir(this.templateDir);
    const layoutsDir = path.join(this.templateDir, 'layouts');
    if (fs.existsSync(layoutsDir)) {
      const entries = fs.readdirSync(layoutsDir, { withFileTypes: true });
      for (const entry of entries) {
        if (entry.isFile() && entry.name.endsWith('.hbs')) {
          const name = entry.name.replace(/\.hbs$/, '');
          const absPath = path.join(layoutsDir, entry.name);
          this.templates.set(name, Handlebars.compile(fs.readFileSync(absPath, 'utf-8')));
        }
      }
    }
  }

  private loadPartials(): void {
    const partialsDir = path.join(this.templateDir, 'partials');
    if (!fs.existsSync(partialsDir)) return;

    const entries = fs.readdirSync(partialsDir, { withFileTypes: true });
    for (const entry of entries) {
      if (entry.isFile() && entry.name.endsWith('.hbs')) {
        const name = entry.name.replace(/\.hbs$/, '');
        const template = fs.readFileSync(path.join(partialsDir, entry.name), 'utf-8');
        Handlebars.registerPartial(name, template);
      }
    }
  }

  private pageToContext(page: Page): Record<string, unknown> {
    return {
      ...page.frontmatter,
      url: page.url,
      content: page.html,
      raw: page.content,
    };
  }

  render(page: Page, allPages: Page[], siteConfig?: Record<string, unknown>): string {
    const templateName = page.frontmatter.template || 'default';
    const layoutName = page.frontmatter.layout || 'default';

    const template = this.templates.get(templateName);
    if (!template) {
      throw new Error(`Template "${templateName}" not found. Available: ${[...this.templates.keys()].join(', ')}`);
    }

    const pageCtx = this.pageToContext(page);
    const context = {
      ...pageCtx,
      site: siteConfig || {},
      pages: allPages.map(p => this.pageToContext(p)),
    };

    const rendered = template(context);
    const layout = this.templates.get(layoutName);

    if (layout) {
      const layoutContext = { ...context, content: rendered };
      return layout(layoutContext);
    }

    return rendered;
  }

  renderTagPage(
    tag: string,
    tagPages: Page[],
    allPages: Page[],
    siteConfig?: Record<string, unknown>
  ): string {
    const tagTemplate = this.templates.get('tags') || this.templates.get('default');
    if (!tagTemplate) {
      throw new Error('No "tags" or "default" template found');
    }

    const layout = this.templates.get('default');

    const context = {
      tag,
      title: `Tag: ${tag}`,
      pages: tagPages.map(p => this.pageToContext(p)),
      allPages: allPages.map(p => this.pageToContext(p)),
      site: siteConfig || {},
      content: '',
      url: `/tags/${tag}.html`,
    };

    const rendered = tagTemplate(context);

    if (layout) {
      return layout({ ...context, content: rendered });
    }

    return rendered;
  }
}
