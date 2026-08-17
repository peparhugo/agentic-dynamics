import { Page } from '../ssg';
import { Plugin, PluginContext } from '../plugin';
import { TemplateEngine } from '../template-engine';

export class TemplatePlugin implements Plugin {
  name = 'template';
  private engine: TemplateEngine;

  constructor(options: { templatesDir?: string } = {}) {
    this.engine = new TemplateEngine({ templatesDir: options.templatesDir });
  }

  beforeBuild(context: PluginContext): void {
    this.engine = new TemplateEngine({ templatesDir: context.templatesDir });
  }

  renderPage(page: Page): string {
    return this.engine.renderPage(page);
  }

  renderIndex(pages: Page[]): string {
    return this.engine.renderIndex(pages);
  }
}
