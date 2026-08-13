import type { Page } from '../site';

export interface Plugin {
  onStart?(context: BuildContext): void;
  beforeBuild?(context: BuildContext): void;
  afterBuild?(context: BuildContext): void;
  onFile?(page: Page, context: BuildContext): void;
  onEnd?(context: BuildContext): void;
}

export interface BuildContext {
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  pages: Page[];
}
