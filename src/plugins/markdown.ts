import type { Plugin } from '../plugin';
import type { Page } from '../types';
import { markdownToHtml } from '../markdown';

export class MarkdownPlugin implements Plugin {
  readonly name = 'markdown';

  onFile(page: Page): Page {
    page.contentHtml = markdownToHtml(page.content ?? '');
    return page;
  }
}
