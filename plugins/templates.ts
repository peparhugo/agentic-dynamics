import { performance } from 'perf_hooks';
import { hashContent, snapshotPage } from '../src/cache';
import { computePageTemplateHash, loadTemplates, renderIndexTemplate, renderPageTemplate, TemplateBundle } from '../src/templates';
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
 *
 * On incremental builds the page source hash (computed by the markdown plugin)
 * and a template fingerprint are compared against the cached manifest. When
 * both match, the cached rendered HTML is reused and the page counts as
 * skipped; otherwise the page is re-rendered and its output cached.
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

    const templateHash = computePageTemplateHash(page, ctx.templateBundle);
    const entry = ctx.cache ? ctx.cache.get(page.slug) : undefined;
    const sourceHash = page.sourceHash ?? hashContent(page.content);

    if (
      ctx.cache &&
      entry &&
      entry.html != null &&
      entry.sourceHash === sourceHash &&
      entry.templateHash === templateHash
    ) {
      ctx.outputFiles.set(`${page.slug}.html`, entry.html);
      if (ctx.stats) {
        ctx.stats.skipped += 1;
        ctx.stats.timeSavedMs += entry.renderMs || 0;
      }
      return;
    }

    const start = performance.now();
    const html = renderPageForBuild(page, ctx.templateBundle);
    const renderMs = performance.now() - start;

    ctx.outputFiles.set(`${page.slug}.html`, html);
    if (ctx.cache) {
      ctx.cache.set(page.slug, {
        sourceHash,
        templateHash,
        page: snapshotPage(page),
        html,
        renderMs,
      });
    }
    if (ctx.stats) {
      ctx.stats.built += 1;
    }
  }

  afterBuild(ctx: PluginContext): void {
    if (!ctx.templateBundle) {
      throw new Error('templates not loaded');
    }
    ctx.outputFiles.set('index.html', renderIndexForBuild(ctx.pages, ctx.templateBundle));
    if (ctx.stats) {
      ctx.stats.built += 1;
    }
  }
}
