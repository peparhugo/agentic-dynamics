import fs from 'fs';
import type { Plugin, PluginContext } from '../plugin';
import { readPages } from '../markdown';

export class MarkdownPlugin implements Plugin {
  name = 'markdown';

  beforeBuild(ctx: PluginContext): void {
    if (!fs.existsSync(ctx.contentDir)) {
      throw new Error(`content directory not found: ${ctx.contentDir}`);
    }
    ctx.pages = readPages(ctx.contentDir, ctx.cache);
  }
}
