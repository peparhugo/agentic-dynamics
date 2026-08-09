import { readFileSync, existsSync, readdirSync } from 'node:fs';
import { join, extname } from 'node:path';
import Handlebars from 'handlebars';
import { Post, SiteConfig, TemplateContext } from './types';

function safeName(path: string): string {
  return path.replace(/[^a-zA-Z0-9_-]/g, '_');
}

export class Renderer {
  private layouts = new Map<string, Handlebars.TemplateDelegate>();
  private partials = new Map<string, Handlebars.TemplateDelegate>();
  private templates = new Map<string, Handlebars.TemplateDelegate>();
  private templateDir: string;

  constructor(templateDir: string) {
    this.templateDir = templateDir;
    this.loadPartials(join(templateDir, 'partials'));
    this.loadLayouts(join(templateDir, 'layouts'));
  }

  private loadPartials(dir: string): void {
    if (!existsSync(dir)) return;
    for (const file of readdirSync(dir)) {
      if (!file.endsWith('.hbs') && !file.endsWith('.html')) continue;
      const name = safeName(file.replace(extname(file), ''));
      const src = readFileSync(join(dir, file), 'utf-8');
      const tpl = Handlebars.compile(src);
      this.partials.set(name, tpl);
      Handlebars.registerPartial(name, tpl);
    }
  }

  private loadLayouts(dir: string): void {
    if (!existsSync(dir)) return;
    for (const file of readdirSync(dir)) {
      if (!file.endsWith('.hbs') && !file.endsWith('.html')) continue;
      const name = safeName(file.replace(extname(file), ''));
      const src = readFileSync(join(dir, file), 'utf-8');
      const tpl = Handlebars.compile(src);
      this.layouts.set(name, tpl);
    }
  }

  loadTemplate(name: string): Handlebars.TemplateDelegate {
    if (this.templates.has(name)) return this.templates.get(name)!;
    const path = join(this.templateDir, `${name}.hbs`);
    const altPath = join(this.templateDir, `${name}.html`);
    const srcPath = existsSync(path) ? path : altPath;
    if (!existsSync(srcPath)) {
      throw new Error(`Template not found: ${name}`);
    }
    const src = readFileSync(srcPath, 'utf-8');
    const tpl = Handlebars.compile(src);
    this.templates.set(name, tpl);
    return tpl;
  }

  render(templateName: string, context: Record<string, unknown>): string {
    const tpl = this.loadTemplate(templateName);
    return tpl(context);
  }

  renderWithLayout(
    templateName: string,
    layoutName: string,
    context: Record<string, unknown>,
  ): string {
    const body = this.render(templateName, context);
    const layout = this.layouts.get(layoutName);
    if (!layout) {
      throw new Error(`Layout not found: ${layoutName}`);
    }
    return layout({ ...context, body });
  }

  renderPost(post: Post, config: SiteConfig): string {
    const ctx: TemplateContext = {
      site: { title: config.siteTitle, url: config.siteUrl },
      page: {
        title: post.title,
        date: post.date.toISOString(),
        tags: post.tags,
        content: post.html,
      },
    };
    return this.renderWithLayout('post', post.layout, ctx);
  }

  renderIndex(posts: Post[], config: SiteConfig): string {
    const tagCounts = new Map<string, number>();
    for (const p of posts) {
      for (const t of p.tags) {
        tagCounts.set(t, (tagCounts.get(t) || 0) + 1);
      }
    }
    const tags = Array.from(tagCounts.entries()).map(([name, count]) => ({
      name,
      count,
    }));

    const ctx: TemplateContext = {
      site: { title: config.siteTitle, url: config.siteUrl },
      page: { title: config.siteTitle },
      posts,
      tags,
    };
    return this.renderWithLayout('index', 'default', ctx);
  }

  renderTagPage(
    tag: string,
    posts: Post[],
    config: SiteConfig,
  ): string {
    const ctx: TemplateContext = {
      site: { title: config.siteTitle, url: config.siteUrl },
      page: { title: `Tag: ${tag}` },
      posts,
    };
    return this.renderWithLayout('tag', 'default', ctx);
  }
}
