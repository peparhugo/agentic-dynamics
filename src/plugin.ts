import type { Page } from './site';

export interface BuildContext {
  contentDir: string;
  outputDir: string;
  templateDir: string;
  source?: string;
  filename?: string;
  page?: Page;
  pages: Page[];
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
