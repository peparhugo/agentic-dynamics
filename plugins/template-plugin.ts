import * as fs from 'fs';
import * as path from 'path';
import { Page } from '../src/page';
import { Plugin, PluginContext } from '../src/plugin';
import { DEFAULT_LAYOUT_NAME, INDEX_TEMPLATE_NAME, TemplateEngine } from '../src/templates';

/**
 * Built-in plugin that renders each Page through the Handlebars template
 * engine and writes it to disk, then renders and writes the site index once
 * all pages are built.
 */
export function templatePlugin(): Plugin {
  let engine: TemplateEngine;

  return {
    name: 'template',
    beforeBuild(ctx: PluginContext): void {
      engine = new TemplateEngine(ctx.templatesDir);
      fs.mkdirSync(ctx.outputDir, { recursive: true });
    },
    onFile(page: Page, ctx: PluginContext): void {
      const destPath = path.join(ctx.outputDir, page.outputPath);
      fs.mkdirSync(path.dirname(destPath), { recursive: true });
      const html = engine.render(page.template, page.layout, { ...page });
      fs.writeFileSync(destPath, html, 'utf-8');
    },
    afterBuild(pages: Page[], ctx: PluginContext): void {
      const indexPath = path.join(ctx.outputDir, 'index.html');
      const indexHtml = engine.render(INDEX_TEMPLATE_NAME, DEFAULT_LAYOUT_NAME, { title: 'Index', pages });
      fs.writeFileSync(indexPath, indexHtml, 'utf-8');
    },
  };
}
