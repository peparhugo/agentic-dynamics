import { Plugin } from '../plugin';
import { parseContent } from '../parse';

export const markdownPlugin: Plugin = {
  name: 'markdown',
  onFile(page) {
    return parseContent(page.content, page.slug);
  },
};
