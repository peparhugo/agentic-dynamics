import type { BuildOptions, Page } from './types';
import type { SsgConfig } from './config';

export interface SsgContext {
  options: BuildOptions;
  config: SsgConfig;
  engine: import('./engine').SsgEngine;
  pages: Page[];
  templateDir: string;
  startTime: number;
}

export interface Plugin {
  name: string;
  onStart?(ctx: SsgContext): void | Promise<void>;
  beforeBuild?(ctx: SsgContext): void | Promise<void>;
  afterBuild?(ctx: SsgContext): void | Promise<void>;
  onFile?(page: Page, ctx: SsgContext): Page | void | Promise<Page | void>;
  onEnd?(ctx: SsgContext): void | Promise<void>;
}

export type PluginHook =
  | 'onStart'
  | 'beforeBuild'
  | 'afterBuild'
  | 'onFile'
  | 'onEnd';
