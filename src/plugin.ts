import type { Page, Plugin, PluginContext, PluginHook } from './types';

export type { Page, Plugin, PluginContext, PluginHook, SSGConfig } from './types';
export { PLUGIN_HOOKS } from './types';

export class PluginPipeline {
  private readonly plugins: Plugin[] = [];

  add(plugin: Plugin): void {
    this.plugins.push(plugin);
  }

  get size(): number {
    return this.plugins.length;
  }

  list(): Plugin[] {
    return [...this.plugins];
  }

  run(hook: PluginHook, ...args: unknown[]): void {
    for (const plugin of this.plugins) {
      const fn = plugin[hook];
      if (typeof fn === 'function') {
        (fn as (...a: unknown[]) => void).apply(plugin, args);
      }
    }
  }

  async runAsync(hook: PluginHook, ...args: unknown[]): Promise<void> {
    for (const plugin of this.plugins) {
      const fn = plugin[hook];
      if (typeof fn === 'function') {
        await (fn as (...a: unknown[]) => void | Promise<void>).apply(plugin, args);
      }
    }
  }

  onStart(ctx: PluginContext): void {
    this.run('onStart', ctx);
  }

  beforeBuild(ctx: PluginContext): void {
    this.run('beforeBuild', ctx);
  }

  afterBuild(ctx: PluginContext): void {
    this.run('afterBuild', ctx);
  }

  onFile(page: Page, ctx: PluginContext): void {
    this.run('onFile', page, ctx);
  }

  onEnd(ctx: PluginContext): void {
    this.run('onEnd', ctx);
  }
}
