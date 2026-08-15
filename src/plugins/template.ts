import type { Plugin } from '../plugin';
import type { Page } from '../types';
import { TemplateEngine } from '../templates';
import { renderPage, renderIndex } from '../render';

export class TemplatePlugin implements Plugin {
  readonly name = 'template';
  readonly engine: TemplateEngine;

  constructor(templatesDir: string) {
    this.engine = new TemplateEngine(templatesDir);
  }

  async beforeBuild(): Promise<void> {
    await this.engine.load();
  }

  renderPage(page: Page): string {
    return renderPage(page, this.engine);
  }

  renderIndex(pages: Page[]): string {
    return renderIndex(pages, this.engine);
  }
}
