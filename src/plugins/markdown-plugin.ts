import { Plugin, PluginContext, FileContext } from '../plugin.js';
import { parseMarkdown } from '../parser.js';

export class MarkdownPlugin implements Plugin {
  name = 'markdown';
  version = '1.0.0';

  async onFile(context: PluginContext, file: FileContext): Promise<void> {
    if (!file.filename.endsWith('.md')) {
      return;
    }

    const parsed = await parseMarkdown(file.content);
    file.parsed = parsed;
  }
}
