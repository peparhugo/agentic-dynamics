import fs from 'fs';
import path from 'path';
import { Plugin, PluginContext } from '../src/plugin';
import { TemplateEngine, renderIndex } from '../src/template';

/**
 * Built-in plugin responsible for rendering every page through the Handlebars
 * template engine and writing the generated HTML files (including the index)
 * into the output directory.
 */
export class TemplatePlugin implements Plugin {
  readonly name = 'template';
  private engine: TemplateEngine | undefined;

  beforeBuild(ctx: PluginContext): void {
    this.engine = new TemplateEngine({
      templateDir: ctx.templateDir,
      defaultTemplate: ctx.options.defaultTemplate,
      defaultLayout: ctx.options.defaultLayout,
    });
    if (!ctx.options.incremental && !ctx.options.clean) {
      fs.rmSync(ctx.outputDir, { recursive: true, force: true });
    }
    fs.mkdirSync(ctx.outputDir, { recursive: true });
  }

  afterBuild(ctx: PluginContext): void {
    const engine = this.engine ?? new TemplateEngine({ templateDir: ctx.templateDir });
    for (const page of ctx.pages) {
      if (!page.rendered) {
        const start = Date.now();
        page.rendered = engine.renderPage(page);
        page.renderMs = Date.now() - start;
      }
      const filePath = path.join(ctx.outputDir, `${page.slug}.html`);
      fs.mkdirSync(path.dirname(filePath), { recursive: true });
      fs.writeFileSync(filePath, page.rendered, 'utf8');
    }
    fs.writeFileSync(path.join(ctx.outputDir, 'index.html'), renderIndex(ctx.pages), 'utf8');
  }
}
