import { DEFAULT_TEMPLATE_DIR, TemplateEngine } from '../templates';
import { renderPage } from '../render';
import type { Plugin, PluginContext, PluginFile } from '../plugin';

export class TemplatePlugin implements Plugin {
  readonly name = 'templates';

  private readonly engine: TemplateEngine;

  constructor(templatesDir: string = DEFAULT_TEMPLATE_DIR) {
    this.engine = new TemplateEngine(templatesDir);
  }

  async onStart(context: PluginContext): Promise<void> {
    await this.engine.load();
  }

  async onFile(page: PluginFile, context: PluginContext): Promise<void> {
    page.html = this.engine.hasTemplates() ? this.engine.renderPage(page, page.html) : renderPage(page);
  }
}
