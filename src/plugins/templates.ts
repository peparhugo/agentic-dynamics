import type { Page } from '../types';
import type { Plugin, PluginContext } from '../plugin';
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
    const html = engine ? renderPageWithTemplates(page, engine, fallbacks) : renderPage(page);
    ctx.outputs.set(pagePath(page), html);
  }

  async afterBuild(ctx: PluginContext): Promise<void> {
    const engine = ctx.shared.get('templateEngine') as TemplateEngine | null | undefined;
    const html = engine
      ? renderIndexWithTemplates(ctx.pages, engine, fallbacks)
      : renderIndex(ctx.pages);
    ctx.outputs.set('index.html', html);
  }
}
