import type { Page } from './generator.js';

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
  incremental?: boolean;
  clean?: boolean;
}

export interface BuildStats {
  pagesBuilt: number;
  pagesSkipped: number;
  timeSavedMs: number;
}

export interface BuildContext {
  options: Required<BuildOptions>;
  pages: Page[];
  buildPages: Page[];
  cleanBuild: boolean;
  cacheFile: string;
  previousCache: Record<string, { hash: string; renderTimeMs: number }>;
  cache: Record<string, { hash: string; renderTimeMs: number }>;
  stats: BuildStats;
}

export interface Plugin {
  onStart?(context: BuildContext): void | Promise<void>;
  beforeBuild?(context: BuildContext): void | Promise<void>;
  afterBuild?(context: BuildContext): void | Promise<void>;
  onFile?(page: Page, context: BuildContext): void | Promise<void>;
  onEnd?(context: BuildContext): void | Promise<void>;
}
