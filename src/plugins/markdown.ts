import { Page, pageFromFile } from '../page';
import { Plugin } from '../plugin';

export class MarkdownPlugin implements Plugin {
  name = 'markdown';

  onFile(page: Page): Page | void {
    if (!page.filePath) return;
    return pageFromFile(page.filePath);
  }
}
