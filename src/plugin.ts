import { Page, BuildOptions } from './types';
import type { SSG } from './engine';

export interface PluginContext {
  engine: SSG;
  options: BuildOptions;
  pages: Page[];
  currentFile?: string;
  writeFile(relPath: string, content: string): void;
}

export interface Plugin {
  name: string;
  onStart?(ctx: PluginContext): void;
  beforeBuild?(ctx: PluginContext): void;
  afterBuild?(ctx: PluginContext): void;
  onFile?(page: Page, ctx: PluginContext): Page | void;
  onEnd?(ctx: PluginContext): void;
}

export type PluginHook = 'onStart' | 'beforeBuild' | 'afterBuild' | 'onEnd';

export class PluginPipeline {
  constructor(readonly plugins: Plugin[]) {}

  run(hook: PluginHook, ctx: PluginContext): void {
    for (const plugin of this.plugins) {
      const fn = plugin[hook];
      if (fn) fn(ctx);
    }
  }

  runFile(page: Page, ctx: PluginContext): Page {
    let current = page;
    for (const plugin of this.plugins) {
      const fn = plugin.onFile;
      if (!fn) continue;
      const result = fn(current, ctx);
      if (result) current = result;
    }
    return current;
  }
}
