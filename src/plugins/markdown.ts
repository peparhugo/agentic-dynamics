import { parseDirectory } from '../parser';
import { Plugin, PluginContext } from '../plugin';

export class MarkdownPlugin implements Plugin {
  name = 'markdown';

  beforeBuild(context: PluginContext): void {
    context.pages = parseDirectory(context.options.content);
  }
}
