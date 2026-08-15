import { loadTemplates, renderIndexTemplate, renderPageTemplate, TemplateBundle } from '../src/templates';
import { renderIndexHtml, renderPageHtml } from '../src/render';
import { Plugin, PluginContext } from '../src/plugin';
import { Page } from '../src/types';

function renderPageForBuild(page: Page, bundle: TemplateBundle): string {
  if (!bundle.exists) {
    if (page.template) {
      throw new Error(`template not found: "${page.template}" (no templates directory configured)`);
    }
    return renderPageHtml(page);
  }
  return renderPageTemplate(page, bundle);
}

function renderIndexForBuild(pages: Page[], bundle: TemplateBundle): string {
  return renderIndexTemplate(pages, bundle) ?? renderIndexHtml(pages);
}

/**
 * Built-in plugin that renders pages and the site index through Handlebars
 * templates.
 *
 * Templates are loaded during `beforeBuild`; each page is rendered in the
 * `onFile` hook and the index is rendered in `afterBuild`. Rendered output is
 * contributed to the engine's output files so the engine can write it to disk.
 */
export class TemplatePlugin implements Plugin {
  readonly name = 'templates';

  async beforeBuild(ctx: PluginContext): Promise<void> {
    ctx.templateBundle = await loadTemplates(ctx.options.templatesDir ?? 'templates');
  }

  onFile(page: Page, ctx: PluginContext): void {
    if (!ctx.templateBundle) {
      throw new Error('templates not loaded');
    }
    ctx.outputFiles.set(`${page.slug}.html`, renderPageForBuild(page, ctx.templateBundle));
  }

  afterBuild(ctx: PluginContext): void {
    if (!ctx.templateBundle) {
      throw new Error('templates not loaded');
    }
    ctx.outputFiles.set('index.html', renderIndexForBuild(ctx.pages, ctx.templateBundle));
  }
}
