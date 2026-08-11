import { Page } from './types';
import { SsgCacheManifest } from './cache';

export interface BuildContext {
  contentDir: string;
  outputDir: string;
  templatesDir?: string;
  cache?: SsgCacheManifest | null;
  cachePath?: string;
  skippedSlugs?: Set<string>;
  templatesHash?: string;
}

export interface Plugin {
  name: string;
  setContext?(context: BuildContext): void;
  onStart?(): void;
  beforeBuild?(): void;
  onFile?(page: Page): void;
  afterBuild?(pages: Page[]): void;
  onEnd?(): void;
}
