import { SiteEngine, sortPages } from './engine';
import { findMarkdownFiles, readPages } from './markdown';
import {
  renderPage,
  renderIndex,
  DEFAULT_TEMPLATES_DIR,
} from './template';
import { BuildResult } from './types';

export const DEFAULT_CONTENT_DIR = 'content';
export const DEFAULT_OUTPUT_DIR = 'dist';

export { renderPage, renderIndex } from './template';
export { findMarkdownFiles, readPages } from './markdown';
export { sortPages } from './engine';

export function buildSite(
  contentDir: string,
  outputDir: string,
  templatesDir: string = DEFAULT_TEMPLATES_DIR
): BuildResult {
  const engine = new SiteEngine({ contentDir, outputDir, templatesDir });
  return engine.build();
}
