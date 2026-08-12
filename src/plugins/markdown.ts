import { Plugin, SsgContext } from '../plugin';
import { Page } from '../types';
import { buildPage } from '../core';

export class MarkdownPlugin implements Plugin {
  name = 'markdown';

  async onFile(page: Page, ctx: SsgContext): Promise<Page> {
    return buildPage(ctx.options.contentDir, page.source);
  }
}
