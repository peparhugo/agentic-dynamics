import { Page } from './types';
import { TemplateEngine } from './templates';

export interface BuildContext {
  config: SsgConfig;
  pages: Page[];
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  engine?: TemplateEngine;
  port?: number;
  [key: string]: any;
}

export interface Plugin {
  name: string;
  onStart?(context: BuildContext): Promise<void> | void;
  beforeBuild?(context: BuildContext): Promise<void> | void;
  onFile?(page: Page, context: BuildContext): Promise<void> | void;
  afterBuild?(context: BuildContext): Promise<void> | void;
  onEnd?(context: BuildContext): Promise<void> | void;
}

export interface SsgConfig {
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  port?: number;
  plugins?: (string | Plugin)[];
}
