import fs from 'fs';
import path from 'path';
import type { Plugin, PluginContext } from '../plugin';
import { Page, BuildResult } from '../types';
import { TemplateEngine, renderPage, renderIndex } from '../template';

export class TemplatePlugin implements Plugin {
  name = 'template';
  private engine?: TemplateEngine;

  beforeBuild(ctx: PluginContext): void {
    this.engine = new TemplateEngine(ctx.templatesDir);
  }

  onFile(page: Page, ctx: PluginContext): Page | void {
    if (!this.engine) this.engine = new TemplateEngine(ctx.templatesDir);
    const html = renderPage(page, this.engine);
    const name = `${page.slug}.html`;
    fs.writeFileSync(path.join(ctx.outputDir, name), html, 'utf8');
    ctx.files.push(name);
  }

  afterBuild(ctx: PluginContext, _result: BuildResult): void {
    if (!this.engine) this.engine = new TemplateEngine(ctx.templatesDir);
    const indexHtml = renderIndex(ctx.pages, this.engine);
    fs.writeFileSync(path.join(ctx.outputDir, 'index.html'), indexHtml, 'utf8');
    if (!ctx.files.includes('index.html')) ctx.files.push('index.html');
  }
}
