import type { Page } from './types';
import type { SiteContext } from './engine';
import type { SiteBuildResult } from './build';

export type PluginHook = 'onStart' | 'beforeBuild' | 'afterBuild' | 'onFile' | 'onEnd';

export interface PluginContext {
  contentDir: string;
  outputDir: string;
  templatesDir?: string;
  port?: number;
  pages: Page[];
  site?: SiteContext;
  lastResult?: SiteBuildResult;
  rebuild?: () => SiteBuildResult;
  onBuild?: (result: SiteBuildResult) => void;
  onError?: (err: Error) => void;
  [key: string]: unknown;
}

export interface Plugin {
  readonly name: string;
  onStart?(ctx: PluginContext): void;
  beforeBuild?(ctx: PluginContext): void;
  afterBuild?(ctx: PluginContext): void;
  onFile?(page: Page, ctx: PluginContext): void;
  onEnd?(ctx: PluginContext): void;
}

export class PluginPipeline {
  private readonly plugins: Plugin[];

  constructor(plugins: Iterable<Plugin> = []) {
    this.plugins = [...plugins];
  }

  register(plugin: Plugin): this {
    this.plugins.push(plugin);
    return this;
  }

  runHook(hook: PluginHook, ...args: unknown[]): void {
    for (const plugin of this.plugins) {
      const method = plugin[hook];
      if (typeof method === 'function') {
        (method as (...hookArgs: unknown[]) => void).apply(plugin, args);
      }
    }
  }
}
