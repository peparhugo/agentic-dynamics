import * as fs from 'fs';
import * as path from 'path';
import { parseFrontmatter } from '../src/frontmatter';
import { renderMarkdown } from '../src/render';
import type { Plugin, PluginContext } from '../src/plugin';
import type { Page } from '../src/types';

/**
 * Built-in plugin that turns each discovered Markdown file into a page:
 * parses its frontmatter, renders the Markdown body to HTML, and fills in
 * title/date/tags/layout metadata (falling back to the slug-derived title
 * when frontmatter omits one).
 */
export class MarkdownPlugin implements Plugin {
  readonly name = 'markdown';

  onFile(page: Page, ctx: PluginContext): Page {
    const filePath = path.join(ctx.contentDir, page.sourcePath);
    const raw = fs.readFileSync(filePath, 'utf8');
    const { data, content } = parseFrontmatter(raw);
    const html = renderMarkdown(content);

    const title = typeof data.title === 'string' && data.title.trim() ? data.title : page.slug;
    const date = typeof data.date === 'string' && data.date.trim() ? data.date : undefined;
    const tags = Array.isArray(data.tags) ? data.tags.map(String) : [];
    const layout = typeof data.layout === 'string' && data.layout.trim() ? data.layout.trim() : undefined;

    return { ...page, title, date, tags, html, layout };
  }
}
