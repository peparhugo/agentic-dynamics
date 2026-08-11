import { Page } from './types';
import { Plugin, PluginContext, SSGOptions } from './plugin';
import { DevServerPlugin, ServerInstance } from './plugins/devserver';

export class SSGEngine {
  private plugins: Plugin[] = [];
  private context: PluginContext;

  constructor(options: SSGOptions) {
    this.context = {
      pages: [],
      options,
    };
  }

  get pages(): Page[] {
    return this.context.pages;
  }

  register(plugin: Plugin): void {
    this.plugins.push(plugin);
  }

  async build(): Promise<void> {
    await this.runHook('onStart');
    await this.runHook('beforeBuild');

    for (let i = 0; i < this.context.pages.length; i++) {
      this.context.pages[i] = await this.runOnFile(this.context.pages[i]);
    }

    await this.runHook('afterBuild');
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
