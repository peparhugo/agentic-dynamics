import type { Page } from './index.js';

export type PluginHook = void | Promise<void>;

export interface Plugin {
  onStart?(): PluginHook;
  beforeBuild?(): PluginHook;
  afterBuild?(): PluginHook;
  onFile?(page: Page): PluginHook;
  onEnd?(): PluginHook;
}

export interface SsgConfig {
  plugins?: Plugin[];
}
