import fs from 'fs';
import { Plugin } from '../plugin';
import { createTemplateEngine, TemplateEngine } from '../templates';
import { renderIndex, renderPage } from '../render';
import { resolveTemplatesDir } from '../cache';

export function createTemplatePlugin(): Plugin {
  let engine: TemplateEngine | null = null;

  return {
    name: 'template',
    beforeBuild(ctx) {
      const dir = resolveTemplatesDir(ctx.options.contentDir, ctx.options.templatesDir);
      engine = fs.existsSync(dir) ? createTemplateEngine(dir) : null;
    },
    onFile(page) {
      const html = engine ? (engine.renderPage(page) ?? renderPage(page)) : renderPage(page);
      return { ...page, html };
    },
    afterBuild(ctx) {
      const index = engine
        ? (engine.renderIndex(ctx.pages) ?? renderIndex(ctx.pages))
        : renderIndex(ctx.pages);
      ctx.writeFile('index.html', index);
    },
  };
}
