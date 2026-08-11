import { parseDirectory, ParseStats } from '../parser';
import { Plugin, PluginContext } from '../plugin';

export class MarkdownPlugin implements Plugin {
  name = 'markdown';

  beforeBuild(context: PluginContext): void {
    const parseStats: ParseStats = { parsed: 0, skipped: 0 };
    context.pages = parseDirectory(
      context.options.content,
      context.cache,
      parseStats
    );
  }
}
