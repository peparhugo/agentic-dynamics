import * as fs from 'fs';
import * as path from 'path';
import { TemplateEngine } from '../templateEngine';
import { renderIndex, renderPage } from '../templates';
import { Plugin, PluginContext } from '../plugin';
import { Page } from '../types';

const DEFAULT_STYLESHEET = `body { font-family: sans-serif; max-width: 40rem; margin: 2rem auto; padding: 0 1rem; line-height: 1.6; }
header { margin-bottom: 2rem; }
.page-list { list-style: none; padding: 0; }
.page-list li { margin-bottom: 0.5rem; }
.tags { list-style: none; padding: 0; display: flex; gap: 0.5rem; }
.tags li { background: #eee; border-radius: 0.25rem; padding: 0.1rem 0.5rem; font-size: 0.85rem; }
`;

function writeFile(filePath: string, contents: string): void {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, contents, 'utf-8');
}

/**
 * Built-in plugin that renders each page to HTML (via a Handlebars
 * TemplateEngine when `templatesDir` is set, falling back to the built-in
 * renderer otherwise) and writes it, plus the site index and default
 * stylesheet, to `outputDir`.
 */
export function createTemplatePlugin(): Plugin {
  let engine: TemplateEngine | undefined;

  return {
    name: 'template',
    beforeBuild(ctx: PluginContext) {
      const { outputDir, templatesDir } = ctx.options;
      fs.mkdirSync(outputDir, { recursive: true });
      engine = templatesDir && fs.existsSync(templatesDir) ? new TemplateEngine(templatesDir) : undefined;
    },
    onFile(page: Page, ctx: PluginContext) {
      const html = engine?.renderPage(page, ctx.pages) ?? renderPage(page);
      writeFile(path.join(ctx.options.outputDir, page.outputFile), html);
    },
    afterBuild(ctx: PluginContext) {
      const indexHtml = engine?.renderIndex(ctx.pages) ?? renderIndex(ctx.pages);
      writeFile(path.join(ctx.options.outputDir, 'index.html'), indexHtml);
      writeFile(path.join(ctx.options.outputDir, 'style.css'), DEFAULT_STYLESHEET);
    },
  };
}
