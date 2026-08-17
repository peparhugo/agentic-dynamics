import { TemplateEngine } from '../templates';
import { Page, Plugin } from '../plugin';
import { pageContext } from '../render';

export class TemplatePlugin implements Plugin {
  name = 'templates';

  private readonly engine: TemplateEngine;

  constructor(templatesDir: string) {
    this.engine = new TemplateEngine(templatesDir);
  }

  onFile(page: Page): void {
    page.rendered = this.engine.render(
      page.template,
      page.layout,
      pageContext(page)
    );
  }
}
