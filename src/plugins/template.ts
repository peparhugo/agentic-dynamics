/**
 * Built-in plugin that renders pages through Handlebars templates, layouts
 * and partials. When no templates directory exists it falls back to the
 * built-in renderers.
 */

import { renderIndex, renderPage } from '../render';
import {
  DEFAULT_TEMPLATES_DIR,
  TEMPLATE_EXTENSION,
  hasTemplates,
  loadTemplates,
  renderIndexWithTemplates,
  renderPageWithTemplates,
} from '../templates';
import type { Templates } from '../templates';
import type { Plugin, PluginContext } from '../plugin';
import type { Page } from '../types';

/** Plugin name used to identify the template plugin. */
export const TEMPLATE_PLUGIN_NAME = 'templates';

/**
 * Loads the templates directory during `beforeBuild` and produces the final
 * HTML for every page and for the site index into `context.outputs`.
 */
export class TemplatePlugin implements Plugin {
  readonly name = TEMPLATE_PLUGIN_NAME;

  private templatesDir: string | null = null;
  private templates: Templates | null = null;

  beforeBuild(context: PluginContext): void {
    const templatesDir = context.options.templatesDir ?? DEFAULT_TEMPLATES_DIR;
    this.templatesDir = templatesDir;
    this.templates = hasTemplates(templatesDir) ? loadTemplates(templatesDir) : null;
  }

  onFile(page: Page, context: PluginContext): void {
    context.outputs[page.outputName] = this.templates
      ? renderPageWithTemplates(page, this.templates)
      : renderPage(page);
  }

  afterBuild(context: PluginContext): void {
    if (!this.templates || !this.templatesDir) return;
    if (this.templates.templates.has(`index.${TEMPLATE_EXTENSION}`)) {
      context.outputs['index.html'] = renderIndexWithTemplates(context.pages, this.templates);
    }
  }
}
