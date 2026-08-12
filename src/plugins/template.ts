import fs from 'fs';
import path from 'path';
import type { Page, Plugin, PluginContext } from '../types';
import { loadTemplates } from '../templates';
import { renderIndexWithTemplates, renderPageWithTemplates } from '../render';

export class TemplatePlugin implements Plugin {
  readonly name = 'template';

  beforeBuild(ctx: PluginContext): void {
    ctx.templates = loadTemplates(ctx.templatesDir);
  }

  onFile(page: Page, ctx: PluginContext): void {
    const html = renderPageWithTemplates(page, ctx.templates);
    fs.writeFileSync(path.join(ctx.outputDir, `${page.slug}.html`), html, 'utf8');
  }

  afterBuild(ctx: PluginContext): void {
    const html = renderIndexWithTemplates(ctx.pages, ctx.templates);
    fs.writeFileSync(path.join(ctx.outputDir, 'index.html'), html, 'utf8');
  }
}
