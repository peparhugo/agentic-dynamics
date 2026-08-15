import { parseMarkdown } from '../src/markdown';
import { Plugin, PluginContext } from '../src/plugin';
import { Page } from '../src/types';

/**
 * Built-in plugin that parses raw Markdown content into structured pages.
 *
 * Runs during the `onFile` hook: it reads the raw source (frontmatter +
 * body) handed to it by the engine and replaces the placeholder page with
 * fully parsed page data, leaving template/layout rendering to later plugins.
 */
export class MarkdownPlugin implements Plugin {
  readonly name = 'markdown';

  async onFile(page: Page, _ctx: PluginContext): Promise<void> {
    const parsed = parseMarkdown(page.content, page.sourcePath, page.slug);
    page.slug = parsed.slug;
    page.title = parsed.title;
    page.date = parsed.date;
    page.tags = parsed.tags;
    page.content = parsed.content;
    page.html = parsed.html;
    page.sourcePath = parsed.sourcePath;
    page.template = parsed.template;
    page.layout = parsed.layout;
    page.data = parsed.data;
  }
}
