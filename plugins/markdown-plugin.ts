import { renderMarkdown } from '../src/markdown';
import { Plugin } from '../src/plugin';

/** Renders each page's raw Markdown content into an HTML body fragment. */
export function markdownPlugin(): Plugin {
  return {
    name: 'markdown',
    onFile(page) {
      page.body = renderMarkdown(page.content);
    },
  };
}
