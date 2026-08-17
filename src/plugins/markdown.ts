import { renderMarkdown } from '../markdown';
import type { Plugin } from '../plugin';
import type { Page } from '../types';

export class MarkdownPlugin implements Plugin {
  name = 'markdown';

  onFile(page: Page): void {
    const markdown = (page as Page & { markdown?: string }).markdown;
    if (typeof markdown === 'string') {
      page.html = renderMarkdown(markdown);
    }
  }
}
