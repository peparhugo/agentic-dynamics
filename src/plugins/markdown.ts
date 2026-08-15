import { Plugin, PluginContext } from '../plugin';
import { Page } from '../types';
import { loadPages } from '../markdown';

export class MarkdownPlugin implements Plugin {
  name = 'markdown';

  beforeBuild(context: PluginContext): void {
    context.pages = loadPages(context.contentDir);
  }

  onFile(page: Page, _context: PluginContext): Page {
    return page;
  }
}
