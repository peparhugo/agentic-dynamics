import fs from 'fs';
import path from 'path';
import { Plugin } from '../src/plugin';
import { getTemplateEngine } from '../src/templates';

/**
 * Wraps each page's rendered body in its Handlebars layout, and writes the
 * site index page once every file in a build pass has been processed.
 */
export function templatePlugin(): Plugin {
  return {
    name: 'template',
    onFile(page, ctx) {
      const engine = getTemplateEngine(ctx.templatesDir);
      page.html = engine.renderPage(
        { title: page.title, date: page.date, tags: page.tags, body: page.body },
        page.template
      );
    },
    afterBuild(pages, ctx) {
      if (!ctx.outputDir) return;
      const engine = getTemplateEngine(ctx.templatesDir);
      fs.writeFileSync(path.join(ctx.outputDir, 'index.html'), engine.renderIndex(pages), 'utf-8');
    },
  };
}
