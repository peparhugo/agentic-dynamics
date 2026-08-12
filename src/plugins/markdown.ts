import { parseMarkdown, renderMarkdown } from '../markdown';
import { normalizeTags, pageTitle } from '../render';
import type { Plugin, PluginContext, PluginFile } from '../plugin';

export class MarkdownPlugin implements Plugin {
  readonly name = 'markdown';

  async onFile(page: PluginFile, context: PluginContext): Promise<void> {
    const { data, body } = parseMarkdown(page.raw);
    page.title = (data.title && data.title.trim()) || pageTitle(page.source);
    page.date = (data.date && data.date.trim()) || '';
    page.tags = normalizeTags(data.tags);
    page.html = renderMarkdown(body);
    page.template = typeof data.template === 'string' && data.template.trim() ? data.template.trim() : undefined;
    page.layout = typeof data.layout === 'string' && data.layout.trim() ? data.layout.trim() : undefined;
    page.data = { ...(data as Record<string, unknown>) };
  }
}
