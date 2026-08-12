import type { Page } from '../types';
import type { Plugin, PluginContext } from '../plugin';
import { BuildCache, CACHE_KEY } from '../cache';
import {
  loadTemplateEngine,
  renderPageWithTemplates,
  renderIndexWithTemplates,
  type FallbackRenderers,
  type TemplateEngine,
} from '../templates';
import {
  pagePath,
  renderDocument,
  renderIndex,
  renderIndexBody,
  renderPage,
} from '../render';

const fallbacks: FallbackRenderers = {
  document: renderDocument,
  indexBody: renderIndexBody,
  indexDocument: renderIndex,
};

export class TemplatePlugin implements Plugin {
  name = 'templates';

  async beforeBuild(ctx: PluginContext): Promise<void> {
    const engine = await loadTemplateEngine(ctx.options.templateDir ?? 'templates');
    ctx.shared.set('templateEngine', engine);
  }

  async onFile(page: Page, ctx: PluginContext): Promise<void> {
    const engine = ctx.shared.get('templateEngine') as TemplateEngine | null | undefined;
    const cache = ctx.shared.get(CACHE_KEY) as BuildCache | undefined;
    const output = pagePath(page);
    if (cache && page.sourceFile && cache.isSkipped(output)) {
      ctx.outputs.set(output, cache.cachedHtml(output));
      return;
    }
    const html = engine ? renderPageWithTemplates(page, engine, fallbacks) : renderPage(page);
    ctx.outputs.set(output, html);
    if (cache && page.sourceFile) {
      cache.recordRendered(page.sourceFile, output, html);
    }
  }

  async afterBuild(ctx: PluginContext): Promise<void> {
    const engine = ctx.shared.get('templateEngine') as TemplateEngine | null | undefined;
    const cache = ctx.shared.get(CACHE_KEY) as BuildCache | undefined;
    if (cache && (await cache.shouldSkipIndex())) {
      cache.skipIndex();
      ctx.outputs.set('index.html', cache.cachedIndexHtml());
      return;
    }
    const startedAt = cache ? Date.now() : 0;
    const html = engine
      ? renderIndexWithTemplates(ctx.pages, engine, fallbacks)
      : renderIndex(ctx.pages);
    ctx.outputs.set('index.html', html);
    if (cache) {
      cache.recordIndex(html, Date.now() - startedAt);
    }
  }
}
