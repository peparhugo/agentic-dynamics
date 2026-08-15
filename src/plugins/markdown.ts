/**
 * Built-in plugin that converts the Markdown body of every page into HTML.
 */

import { markdownToHtml } from '../markdown';
import type { Plugin, PluginContext } from '../plugin';
import type { Page } from '../types';

/** Plugin name used to identify the Markdown plugin. */
export const MARKDOWN_PLUGIN_NAME = 'markdown';

/**
 * Converts `page.content` (the raw Markdown body) into `page.html` when it
 * has not been rendered yet. Pages loaded through the content loader already
 * carry their rendered HTML, in which case this is a no-op.
 */
export class MarkdownPlugin implements Plugin {
  readonly name = MARKDOWN_PLUGIN_NAME;

  onFile(page: Page, _context: PluginContext): void {
    if (!page.html) {
      page.html = markdownToHtml(page.content);
    }
  }
}
