import type { Page } from './site';

export interface BuildContext {
  contentDir: string;
  outputDir: string;
  templateDir: string;
  source?: string;
  filename?: string;
  page?: Page;
  pages: Page[];
  /** Incremental state consumed by the built-in renderer. */
  skipRender?: boolean;
  cachedHtml?: string;
  cachedRenderTimeMs?: number;
  renderedHtml?: string;
  renderTimeMs?: number;
  stats: BuildStats;
}

export interface BuildStats {
  pagesBuilt: number;
  pagesSkipped: number;
  timeSavedMs: number;
}

export interface Plugin {
  onStart?(context: BuildContext): void | Promise<void>;
  beforeBuild?(context: BuildContext): void | Promise<void>;
  afterBuild?(context: BuildContext): void | Promise<void>;
  onFile?(context: BuildContext): void | Promise<void>;
  onEnd?(context: BuildContext): void | Promise<void>;
}

export interface SsgConfig {
  plugins?: Plugin[];
}
