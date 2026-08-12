import { markdownToHtml } from '../markdown';
import type { Plugin, SsgContext } from '../plugin';
import type { Page } from '../types';

export class MarkdownPlugin implements Plugin {
  readonly name = 'markdown';

  async onFile(page: Page, _context: SsgContext): Promise<void> {
    page.html = await markdownToHtml(page.content);
  }
}
