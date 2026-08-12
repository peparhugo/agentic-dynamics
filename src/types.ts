import type { Plugin } from './plugin';

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templateDir?: string;
  defaultTemplate?: string;
  defaultLayout?: string;
  configPath?: string;
  plugins?: Plugin[];
  /**
   * Incremental build: reuse cached pages whose source and templates have not
   * changed, skipping their parse and render work.
   */
  incremental?: boolean;
  /**
   * Clean build: ignore any existing cache and rebuild every page.
   */
  clean?: boolean;
}

/**
 * Summary of an (incremental) build run.
 */
export interface BuildStats {
  /** Total number of source pages discovered. */
  total: number;
  /** Number of pages that were actually (re)built. */
  built: number;
  /** Number of pages reused from the cache. */
  skipped: number;
  /** Approximate milliseconds saved by skipping cached pages. */
  timeSaved: number;
  /** Path of the cache manifest, when one was used. */
  cacheFile?: string;
}

export interface Frontmatter {
  title?: string;
  date?: string | Date;
  tags?: string[] | string;
  template?: string;
  layout?: string;
  [key: string]: unknown;
}

export interface Page {
  sourcePath: string;
  slug: string;
  title: string;
  date: string;
  tags: string[];
  template?: string;
  layout?: string;
  content: string;
  html: string;
  rendered?: string;
  /** Internal: how long template rendering took for this page (ms). */
  renderMs?: number;
}
