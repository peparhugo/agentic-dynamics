import * as fs from 'fs';
import * as path from 'path';
import { Page } from '../src/types';
import { Plugin, BuildContext } from '../src/plugin';
import { TemplateEngine } from '../src/template-engine';
import { pageTemplate, indexTemplate } from '../src/template';

export class TemplatePlugin implements Plugin {
  name = 'template';
  private context: BuildContext | null = null;

  setContext(context: BuildContext): void {
    this.context = context;
  }

  afterBuild(pages: Page[]): void {
    const ctx = this.context;
    if (!ctx) return;

    const { outputDir, templatesDir } = ctx;

    let engine: TemplateEngine | undefined;
    if (templatesDir && fs.existsSync(templatesDir)) {
      engine = new TemplateEngine({ templatesDir: path.resolve(templatesDir) });
    }

    const absoluteOutput = path.resolve(outputDir);
    if (!fs.existsSync(absoluteOutput)) {
      fs.mkdirSync(absoluteOutput, { recursive: true });
    }

    for (const page of pages) {
      let html: string;
      if (engine) {
        const tplName = page.template || (engine.hasTemplate('default') ? 'default' : undefined);
        const lytName = page.layout || (engine.hasLayout('default') ? 'default' : undefined);
        html = engine.render(page, tplName, lytName);
      } else {
        html = pageTemplate(page);
      }
      fs.writeFileSync(path.join(absoluteOutput, `${page.slug}.html`), html);
    }

    let indexHtml: string;
    if (engine && engine.hasIndex()) {
      indexHtml = engine.renderIndex(pages);
    } else {
      indexHtml = indexTemplate(pages);
    }
    fs.writeFileSync(path.join(absoluteOutput, 'index.html'), indexHtml);
  }
}
