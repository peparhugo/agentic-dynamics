import { Plugin, PluginContext } from '../src/plugin';
import { Page } from '../src/types';
import { parseMarkdownFile } from '../src/parser';

/**
 * Built-in plugin responsible for reading Markdown source files, parsing
 * frontmatter, and rendering Markdown to HTML for every content page.
 */
export class MarkdownPlugin implements Plugin {
  readonly name = 'markdown';

  onFile(page: Page, ctx: PluginContext): Page {
    return parseMarkdownFile(page.sourcePath, ctx.contentDir);
  }
}
