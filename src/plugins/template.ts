import { createTemplateEngine } from '../engine';
import type { TemplateEngine } from '../engine';
import type { Plugin, PluginContext } from '../plugin';
import type { Page } from '../types';

export class TemplatePlugin implements Plugin {
  name = 'template';
  private engine: TemplateEngine | undefined;

  async beforeBuild(context: PluginContext): Promise<void> {
    this.engine = await createTemplateEngine(context.templatesDir);
  }

  renderPage(page: Page): string {
    if (!this.engine) {
      throw new Error('TemplatePlugin: beforeBuild() must run before renderPage()');
    }
    return this.engine.renderPage(page);
  }

  renderIndex(pages: Page[]): string {
    if (!this.engine) {
      throw new Error('TemplatePlugin: beforeBuild() must run before renderIndex()');
    }
    return this.engine.renderIndex(pages);
  }
}
