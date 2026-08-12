import { Plugin, BuildContext } from '../src/plugin';
import { parseMarkdownFiles } from '../src/parser';

export const MarkdownPlugin: Plugin = {
  name: 'markdown',

  beforeBuild(context: BuildContext): void {
    context.pages = parseMarkdownFiles(context.contentDir);
  },
};
