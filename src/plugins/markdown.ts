import type { Plugin, PluginContext } from '../types';
import { readPages, sortPages } from '../markdown';

export class MarkdownPlugin implements Plugin {
  readonly name = 'markdown';

  beforeBuild(ctx: PluginContext): void {
    ctx.pages = sortPages(readPages(ctx.contentDir));
  }
}
