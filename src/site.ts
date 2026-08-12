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
export { CacheManager, CACHE_FILE } from './cache';

export interface BuildOptions {
  templatesDir?: string;
  incremental?: boolean;
  clean?: boolean;
}

export function buildSite(
  contentDir: string,
  outputDir: string,
  templatesOrOptions?: string | BuildOptions
): BuildResult {
  const templatesDir =
    typeof templatesOrOptions === 'string'
      ? templatesOrOptions
      : (templatesOrOptions?.templatesDir ?? DEFAULT_TEMPLATES_DIR);
  const incremental =
    typeof templatesOrOptions === 'string'
      ? false
      : (templatesOrOptions?.incremental ?? false);
  const clean =
    typeof templatesOrOptions === 'string'
      ? false
      : (templatesOrOptions?.clean ?? false);
  const engine = new SiteEngine({
    contentDir,
    outputDir,
    templatesDir,
    incremental,
    clean,
  });
  return engine.build();
}
