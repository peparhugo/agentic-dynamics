import fs from 'fs';
import path from 'path';
import { Plugin, BuildContext } from '../src/plugin';
import { TemplateEngine } from '../src/templates';
import { Page } from '../src/types';

export const TemplatePlugin: Plugin = {
  name: 'template',

  beforeBuild(context: BuildContext): void {
    context.engine = new TemplateEngine(context.templatesDir);
    fs.mkdirSync(context.outputDir, { recursive: true });
  },

  onFile(page: Page, context: BuildContext): void {
    const engine = context.engine!;
    const body = engine.renderPage(page);
    const html = engine.renderLayout(page.frontmatter.title, body, page.frontmatter.layout);
    fs.writeFileSync(path.join(context.outputDir, `${page.slug}.html`), html, 'utf-8');
  },

  afterBuild(context: BuildContext): void {
    const engine = context.engine!;
    const indexBody = engine.renderIndex(context.pages);
    const indexHtml = engine.renderLayout('Site Index', indexBody);
    fs.writeFileSync(path.join(context.outputDir, 'index.html'), indexHtml, 'utf-8');
  },
};
