import { pageToContext, renderPage } from '../render';
import { Page, Plugin } from '../plugin';
import { TemplateEngine } from '../templates';

/**
 * Built-in plugin that renders each page through a Handlebars template.
 *
 * It prefers the layout named by the page's `template` metadata, falling back
 * to the `default` layout, and finally to the built-in HTML page renderer when
 * no layout matches. The final full-page HTML is stored in `page.rendered`.
 */
export class TemplatePlugin implements Plugin {
  name = 'template';

  private engine: TemplateEngine;

  constructor(templatesDir: string) {
    this.engine = new TemplateEngine(templatesDir);
  }

  onFile(page: Page): void {
    const rendered = this.engine.render(page.template, pageToContext(page));
    page.rendered = rendered ?? renderPage(page);
  }
}
