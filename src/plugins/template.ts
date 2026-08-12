import fs from 'fs';
import path from 'path';
import type { Page, Plugin, PluginContext } from '../types';
import { loadTemplates } from '../templates';
import { renderIndexWithTemplates, renderPageWithTemplates } from '../render';
import {
  emptyStats,
  indexTemplateHash,
  templateHashFor,
} from '../cache';

export class TemplatePlugin implements Plugin {
  readonly name = 'template';

  beforeBuild(ctx: PluginContext): void {
    ctx.templates = loadTemplates(ctx.templatesDir);
  }

  onFile(page: Page, ctx: PluginContext): void {
    const stats = (ctx.stats = ctx.stats ?? emptyStats());
    const cache = ctx.cache;
    const sourceHash = page.sourceHash;
    const templateHash = templateHashFor(page, ctx.templates);

    const cached = cache?.entries?.[page.slug];
    const reusable =
      ctx.incremental === true &&
      !!cache &&
      !!cached &&
      cached.sourceHash === sourceHash &&
      cached.templateHash === templateHash &&
      typeof cached.html === 'string';

    if (reusable && cached) {
      const outPath = path.join(ctx.outputDir, `${page.slug}.html`);
      if (!fs.existsSync(outPath)) {
        fs.writeFileSync(outPath, cached.html as string, 'utf8');
      }
      stats.pagesSkipped += 1;
      stats.timeSavedMs += cached.buildMs ?? 0;
      return;
    }

    const start = Date.now();
    const html = renderPageWithTemplates(page, ctx.templates);
    fs.writeFileSync(path.join(ctx.outputDir, `${page.slug}.html`), html, 'utf8');
    const buildMs = Date.now() - start;

    stats.pagesBuilt += 1;
    if (cache) {
      cache.entries[page.slug] = {
        sourceHash: sourceHash ?? '',
        templateHash,
        html,
        page,
        buildMs,
        builtAt: new Date().toISOString(),
      };
    }
  }

  afterBuild(ctx: PluginContext): void {
    const stats = (ctx.stats = ctx.stats ?? emptyStats());
    const cache = ctx.cache;
    stats.pages = ctx.pages.length;

    const indexHash = indexTemplateHash(ctx.templates);
    const anyPageChanged = stats.pagesBuilt > 0;
    const pageCountChanged = (cache?.pageCount ?? -1) !== ctx.pages.length;
    const templateChanged = cache?.indexHash !== indexHash;

    if (cache && !anyPageChanged && !pageCountChanged && !templateChanged) {
      stats.timeSavedMs += cache.indexBuildMs ?? 0;
      const indexPath = path.join(ctx.outputDir, 'index.html');
      if (!fs.existsSync(indexPath) && typeof cache.indexHtml === 'string') {
        fs.writeFileSync(indexPath, cache.indexHtml, 'utf8');
      }
      return;
    }

    const start = Date.now();
    const html = renderIndexWithTemplates(ctx.pages, ctx.templates);
    fs.writeFileSync(path.join(ctx.outputDir, 'index.html'), html, 'utf8');
    const buildMs = Date.now() - start;

    if (cache) {
      cache.indexHash = indexHash;
      cache.indexHtml = html;
      cache.indexBuildMs = buildMs;
      cache.pageCount = ctx.pages.length;
    }
  }
}
