import { Frontmatter, Page, markdownToHtml, normalizeTags, parseFrontmatter } from '../ssg';
import { Plugin, PluginContext } from '../plugin';

export class MarkdownPlugin implements Plugin {
  name = 'markdown';

  parseFrontmatter(raw: string): { frontmatter: Frontmatter; content: string } {
    return parseFrontmatter(raw);
  }

  normalizeTags(tags: Frontmatter['tags']): string[] {
    return normalizeTags(tags);
  }

  markdownToHtml(markdown: string): string {
    return markdownToHtml(markdown);
  }

  render(page: Page): Page {
    if (page.content === undefined) {
      return page;
    }
    return { ...page, html: this.markdownToHtml(page.content) };
  }

  onFile(page: Page, _context: PluginContext): Page {
    return this.render(page);
  }
}
