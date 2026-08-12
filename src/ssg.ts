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

export {
  BuildCache,
  CACHE_KEY,
  DEFAULT_CACHE_FILE,
  hashContent,
  hashFile,
  hashTemplateDir,
  loadManifest,
  saveManifest,
  CACHE_VERSION,
} from './cache';

export type {
  BuildStats,
} from './types';

export async function build(options: BuildOptions): Promise<Page[]> {
  const engine = await SSGEngine.fromOptions(options);
  return engine.build(options);
}
