import { Page } from './types';
import { Plugin, PluginContext, SSGOptions } from './plugin';
import { BuildCache, BuildStats } from './cache';
import { DevServerPlugin, ServerInstance } from './plugins/devserver';

export class SSGEngine {
  private plugins: Plugin[] = [];
  private context: PluginContext;
  private cache: BuildCache;

  constructor(options: SSGOptions) {
    const cacheFile = options.cacheFile || '.ssg-cache.json';
    this.cache = new BuildCache(cacheFile);
    this.context = {
      pages: [],
      options,
      cache: this.cache,
      stats: { pagesBuilt: 0, pagesSkipped: 0, timeSavedMs: 0 },
    };
  }

  get pages(): Page[] {
    return this.context.pages;
  }

  get stats(): BuildStats | undefined {
    return this.context.stats;
  }

  register(plugin: Plugin): void {
    this.plugins.push(plugin);
  }

  async build(): Promise<void> {
    const startTime = Date.now();
    const options = this.context.options;

    if (options.clean) {
      this.cache.clear();
    } else if (options.incremental) {
      this.cache.load();
    }

    await this.runHook('onStart');
    await this.runHook('beforeBuild');

    for (let i = 0; i < this.context.pages.length; i++) {
      this.context.pages[i] = await this.runOnFile(this.context.pages[i]);
    }

    await this.runHook('afterBuild');

    if (options.incremental || options.clean) {
      this.cache.save();
    }

    const elapsed = Date.now() - startTime;

    if (this.context.stats && options.incremental) {
      this.context.stats.timeSavedMs = elapsed;
      console.log(
        `Site generated: ${this.context.stats.pagesBuilt} pages built, ` +
          `${this.context.stats.pagesSkipped} pages skipped`
      );
    }
  }

  async serve(): Promise<ServerInstance> {
    await this.runHook('onStart');
    await this.runBuildPipeline();

    const devPlugin = this.plugins.find(
      (p) => p.name === 'devserver'
    ) as DevServerPlugin;
    if (!devPlugin) {
      throw new Error(
        'DevServerPlugin is required for serving but was not registered'
      );
    }

    const rebuildFn = async () => {
      await this.runBuildPipeline();
    };

    return devPlugin.startServer(this.context, rebuildFn);
  }

  async shutdown(): Promise<void> {
    await this.runHook('onEnd');
  }

  private async runBuildPipeline(): Promise<void> {
    await this.runHook('beforeBuild');

    for (let i = 0; i < this.context.pages.length; i++) {
      this.context.pages[i] = await this.runOnFile(this.context.pages[i]);
    }

    await this.runHook('afterBuild');

    console.log(`Site rebuilt (${this.context.pages.length} pages)`);
  }

  private async runHook(
    hook: 'onStart' | 'beforeBuild' | 'afterBuild' | 'onEnd'
  ): Promise<void> {
    for (const plugin of this.plugins) {
      const fn = plugin[hook] as
        | ((context: PluginContext) => void | Promise<void>)
        | undefined;
      if (fn) {
        await fn(this.context);
      }
    }
  }

  private async runOnFile(page: Page): Promise<Page> {
    let result = page;
    for (const plugin of this.plugins) {
      if (plugin.onFile) {
        result = await plugin.onFile(result);
      }
    }
    return result;
  }
}
