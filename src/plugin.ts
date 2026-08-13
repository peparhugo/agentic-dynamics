import type { Page, ResolvedBuildOptions } from './generator.js';

export interface BuildContext {
  options: ResolvedBuildOptions;
  pages: Page[];
}

export interface Plugin {
  onStart?(context: BuildContext): void | Promise<void>;
  beforeBuild?(context: BuildContext): void | Promise<void>;
  afterBuild?(context: BuildContext): void | Promise<void>;
  onFile?(page: Page, context: BuildContext): void | Promise<void>;
  onEnd?(context: BuildContext): void | Promise<void>;
}
