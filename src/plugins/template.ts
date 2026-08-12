import { mkdirSync, writeFileSync } from 'fs';
import { join } from 'path';
import { Page } from '../page';
import { Plugin, PluginContext } from '../plugin';
import { TemplateEngine, loadTemplates } from '../engine';
import { indexHtml, pageHtml } from '../templates';

export class TemplatePlugin implements Plugin {
  name = 'template';

  private engine: TemplateEngine | null = null;

  onStart(context: PluginContext): void {
    this.reload(context);
  }

  beforeBuild(context: PluginContext): void {
    this.reload(context);
  }

  onFile(page: Page, _context: PluginContext): Page {
    page.html = this.renderPage(page);
    return page;
  }

  afterBuild(context: PluginContext, pages: Page[]): void {
    mkdirSync(context.outputDir, { recursive: true });
    for (const page of pages) {
      const html = this.renderPage(page);
      writeFileSync(join(context.outputDir, `${page.slug}.html`), html, 'utf8');
    }
    const index = this.engine ? this.engine.renderIndex(pages) : indexHtml(pages);
    writeFileSync(join(context.outputDir, 'index.html'), index, 'utf8');
  }

  private renderPage(page: Page): string {
    return this.engine ? this.engine.renderPage(page) : pageHtml(page);
  }

  private reload(context: PluginContext): void {
    this.engine = loadTemplates(context.templatesDir);
  }
}
