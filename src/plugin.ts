import type { Page, BuildOptions } from './index';

export interface BuildContext {
  options: Required<BuildOptions>;
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  files: string[];
  pages: Page[];
  cache: BuildCache;
  stats: BuildStats;
  renderCacheEnabled: boolean;
}

export interface CachePage {
  sourceHash: string;
  templateHash: string;
  page: Page;
  renderedHtml?: string;
  renderDurationMs?: number;
}

export interface BuildCache {
  version: 1;
  pages: Record<string, CachePage>;
  stats?: BuildStats;
}

export interface BuildStats {
  pagesBuilt: number;
  pagesSkipped: number;
  timeSaved: number;
}

export interface Plugin {
  onStart?(context: BuildContext): void | Promise<void>;
  beforeBuild?(context: BuildContext): void | Promise<void>;
  afterBuild?(context: BuildContext): void | Promise<void>;
  onFile?(page: Page, context: BuildContext): Page | void | Promise<Page | void>;
  onEnd?(context: BuildContext): void | Promise<void>;
}

export type PluginModule = Plugin | (() => Plugin) | { default: Plugin | (() => Plugin) };
