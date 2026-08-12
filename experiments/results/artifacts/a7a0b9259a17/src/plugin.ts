import { PageData } from './types';

export interface BuildContext {
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  pages: PageData[];
  incremental?: boolean;
  cachedPages?: Map<string, string>;
  buildStats?: { pagesBuilt: number; pagesSkipped: number; timeSavedMs: number };
}

export interface Plugin {
  name: string;
  onStart?(ctx: BuildContext): void | Promise<void>;
  beforeBuild?(ctx: BuildContext): void | Promise<void>;
  afterBuild?(ctx: BuildContext): void | Promise<void>;
  onFile?(page: PageData, ctx: BuildContext): PageData | Promise<PageData>;
  onEnd?(ctx: BuildContext): void | Promise<void>;
}
