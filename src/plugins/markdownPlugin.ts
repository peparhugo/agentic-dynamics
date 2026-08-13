import * as fs from 'fs';
import { loadPages } from '../markdownLoader';
import { Plugin, PluginContext } from '../plugin';

/**
 * Built-in plugin that loads and parses the site's Markdown content.
 * Populates `ctx.pages` during `beforeBuild`, before any `onFile` hook
 * runs.
 */
export function createMarkdownPlugin(): Plugin {
  return {
    name: 'markdown',
    beforeBuild(ctx: PluginContext) {
      const { contentDir } = ctx.options;
      if (!fs.existsSync(contentDir)) {
        throw new Error(`Content directory not found: ${contentDir}`);
      }
      ctx.pages.push(...loadPages(contentDir));
    },
  };
}
