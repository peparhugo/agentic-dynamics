import fs from 'fs';
import { TemplateEngine } from '../engine';
import type { Plugin, PluginContext } from '../plugin';
import type { Page } from '../types';

export class TemplatePlugin implements Plugin {
  readonly name = 'template';

  private engine: TemplateEngine | null = null;

  beforeBuild(ctx: PluginContext): void {
    const dir = ctx.templatesDir ?? 'templates';
    this.engine = fs.existsSync(dir) ? new TemplateEngine(dir) : null;
  }

  onFile(page: Page, ctx: PluginContext): void {
    if (!this.engine || !ctx.site) {
      return;
    }
    page.templated = this.engine.renderPage(page, ctx.site);
  }
}
