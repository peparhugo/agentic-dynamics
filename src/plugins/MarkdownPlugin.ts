import fs from 'fs';
import path from 'path';
import { parseMarkdown, renderMarkdown } from '../parser';
import type { Plugin, PluginContext } from '../plugin';
import type { Page } from '../types';

export class MarkdownPlugin implements Plugin {
  readonly name = 'markdown';

  onFile(page: Page, ctx: PluginContext): void {
    const raw = fs.readFileSync(path.join(ctx.contentDir, page.sourcePath), 'utf-8');
    const { data, body } = parseMarkdown(raw);
    page.data = data;
    page.body = body;
    page.html = renderMarkdown(body);
  }
}
