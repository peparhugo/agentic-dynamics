import { parseMarkdown } from '../markdown';
import { Page, Plugin } from '../plugin';

/**
 * Built-in plugin that parses Markdown documents.
 *
 * The engine creates each `Page` with the raw file source in `content`. This
 * plugin parses the frontmatter, rewrites `content` to the stripped Markdown
 * body and fills `html` with the rendered body HTML.
 */
export class MarkdownPlugin implements Plugin {
  name = 'markdown';

  onFile(page: Page): void {
    const { meta, content, html } = parseMarkdown(page.content);

    page.title = meta.title || page.slug;
    page.date = meta.date;
    page.tags = meta.tags;
    page.template = meta.template;
    page.content = content;
    page.html = html;
  }
}
