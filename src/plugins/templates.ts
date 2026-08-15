import fs from 'fs';
import path from 'path';
import { Plugin, PluginContext } from '../plugin';
import { Page } from '../types';
import { TemplateEngine } from '../templates';

export class TemplatePlugin implements Plugin {
  name = 'templates';

  private engine: TemplateEngine | null = null;

  beforeBuild(context: PluginContext): void {
    this.engine = new TemplateEngine(context.templatesDir);
  }

  onFile(page: Page, context: PluginContext): Page {
    const html = this.requireEngine().renderPage(page, context.pages);
    fs.writeFileSync(path.join(context.outputDir, `${page.slug}.html`), html, 'utf-8');
    context.cache?.setHtml(page.slug, html);
    return page;
  }

  afterBuild(context: PluginContext): void {
    const indexHtml = this.requireEngine().renderIndex(context.pages);
    fs.writeFileSync(path.join(context.outputDir, 'index.html'), indexHtml, 'utf-8');
  }

  private requireEngine(): TemplateEngine {
    if (!this.engine) {
      throw new Error('TemplatePlugin has not been initialized');
    }
    return this.engine;
  }
}
