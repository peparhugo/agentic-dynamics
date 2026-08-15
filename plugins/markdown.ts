import { hashContent, applyParsedPage } from '../src/cache';
import { parseMarkdown } from '../src/markdown';
import { Plugin, PluginContext } from '../src/plugin';
import { Page } from '../src/types';

/**
 * Built-in plugin that parses raw Markdown content into structured pages.
 *
 * Runs during the `onFile` hook: it reads the raw source (frontmatter +
 * body) handed to it by the engine and replaces the placeholder page with
 * fully parsed page data, leaving template/layout rendering to later plugins.
 *
 * On incremental builds the raw source is hashed; when the hash matches the
 * cached manifest the previously parsed page (including its parsed
 * frontmatter and rendered markdown) is restored instead of re-parsing it.
 */
export class MarkdownPlugin implements Plugin {
  readonly name = 'markdown';

  async onFile(page: Page, ctx: PluginContext): Promise<void> {
    const sourceHash = hashContent(page.content);
    page.sourceHash = sourceHash;

    const entry = ctx.cache ? ctx.cache.get(page.slug) : undefined;
    if (entry && entry.sourceHash === sourceHash && entry.page) {
      applyParsedPage(entry.page, page);
      return;
    }

    const parsed = parseMarkdown(page.content, page.sourcePath, page.slug);
    applyParsedPage(parsed, page);
  }
}
