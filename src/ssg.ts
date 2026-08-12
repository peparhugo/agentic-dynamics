import { SSGEngine } from './engine';
import type { BuildOptions, Page } from './types';

export {
  escapeHtml,
  pagePath,
  renderDocument,
  renderPage,
  renderIndexItems,
  renderIndexBody,
  renderIndex,
} from './render';

export { listMarkdownFiles, parseMarkdownFile, MarkdownPlugin } from './plugins/markdown';

export async function build(options: BuildOptions): Promise<Page[]> {
  const engine = await SSGEngine.fromOptions(options);
  return engine.build(options);
}
