import { marked } from 'marked';
import { Plugin } from '../types';

export const MarkdownPlugin: Plugin = {
  name: 'markdown',
  onFile(page): void {
    page.content = marked.parse(page.content, { async: false }) as string;
  },
};
