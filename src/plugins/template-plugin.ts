import fs from 'fs';
import path from 'path';
import { Plugin, PluginContext } from '../plugin';
import { Page } from '../types';
import {
  TemplateEngine,
  DEFAULT_TEMPLATE_NAME,
  DEFAULT_LAYOUT_NAME,
} from '../templates';

function pageSummary(page: Page): Record<string, unknown> {
  return {
    slug: page.slug,
    title: page.title,
    date: page.date,
    tags: page.tags,
    url: `${page.slug}.html`,
  };
}

function buildPageContext(page: Page, pages: Page[]): Record<string, unknown> {
  return {
    ...page.frontmatter,
    title: page.title,
    date: page.date,
    tags: page.tags,
    slug: page.slug,
    content: page.html,
    body: page.html,
    site: {
      pages: pages.map(pageSummary),
    },
  };
}

/**
 * Built-in plugin that renders each page through the template engine and writes
 * the resulting HTML to the output directory. Rendering happens on the
 * `afterBuild` hook so every page (and its metadata) is available for the
 * `site.pages` context used by templates and partials.
 */
export class TemplatePlugin implements Plugin {
  name = 'template';

  private readonly engine: TemplateEngine;

  constructor(private readonly context: PluginContext) {
    this.engine = new TemplateEngine(context.templatesDir, {
      defaultTemplate: context.options.defaultTemplate ?? DEFAULT_TEMPLATE_NAME,
      defaultLayout: context.options.defaultLayout ?? DEFAULT_LAYOUT_NAME,
    });
  }

  afterBuild(): void {
    const { pages, outputDir } = this.context;
    for (const page of pages) {
      const rendered = this.engine.render(page.template, page.layout, buildPageContext(page, pages));
      const outFile = path.join(outputDir, `${page.slug}.html`);
      fs.mkdirSync(path.dirname(outFile), { recursive: true });
      fs.writeFileSync(outFile, rendered);
    }
  }
}
