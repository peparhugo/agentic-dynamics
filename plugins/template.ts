import * as fs from 'fs';
import * as path from 'path';
import { TemplateEngine } from '../src/templates';
import { renderIndexBodyHtml } from '../src/render';
import type { Plugin, PluginContext } from '../src/plugin';
import type { Page } from '../src/types';

const INDEX_LAYOUT_NAME = 'index';

/**
 * Built-in plugin that renders every page through its Handlebars layout and
 * writes the resulting HTML files, then generates and writes the `index.html`
 * listing page once all pages are known.
 */
export class TemplatePlugin implements Plugin {
  readonly name = 'template';

  private engine?: TemplateEngine;

  beforeBuild(ctx: PluginContext): void {
    this.engine = new TemplateEngine(ctx.templatesDir);
  }

  afterBuild(pages: Page[], ctx: PluginContext): void {
    const engine = this.requireEngine();
    const unchangedSourcePaths = ctx.incremental?.unchangedSourcePaths;

    fs.mkdirSync(ctx.outputDir, { recursive: true });

    for (const page of pages) {
      const outPath = path.join(ctx.outputDir, page.outputFile);

      // A page unchanged since the last cached build already has correct
      // output on disk from that build, so re-rendering and rewriting it
      // would just reproduce the same bytes.
      if (unchangedSourcePaths?.has(page.sourcePath) && fs.existsSync(outPath)) {
        continue;
      }

      fs.mkdirSync(path.dirname(outPath), { recursive: true });
      const html = engine.render(page.layout, {
        title: page.title,
        date: page.date,
        tags: page.tags,
        body: page.html,
      });
      fs.writeFileSync(outPath, html, 'utf8');
    }

    const indexLayout = engine.hasLayout(INDEX_LAYOUT_NAME) ? INDEX_LAYOUT_NAME : undefined;
    const indexHtml = engine.render(indexLayout, {
      title: 'All Pages',
      tags: [],
      body: renderIndexBodyHtml(pages),
    });
    fs.writeFileSync(path.join(ctx.outputDir, 'index.html'), indexHtml, 'utf8');
  }

  private requireEngine(): TemplateEngine {
    if (!this.engine) {
      throw new Error('TemplatePlugin: beforeBuild must run before afterBuild');
    }
    return this.engine;
  }
}
