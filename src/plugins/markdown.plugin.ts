import { Plugin, PluginContext } from '../plugin';
import { PageData } from '../page';
import { markdownToHtml } from '../markdown';

export const MarkdownPlugin: Plugin = {
  name: 'markdown',

  onFile: async (page: PageData, _context: PluginContext): Promise<PageData> => {
    return page;
  }
};
