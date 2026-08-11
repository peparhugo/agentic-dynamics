import { Plugin, BuildContext, SsgConfig } from './plugin';
import { Page } from './types';

export class SSG {
  private config: SsgConfig;
  private plugins: Plugin[] = [];

  constructor(config: SsgConfig) {
    this.config = {
      contentDir: config.contentDir || './content',
      outputDir: config.outputDir || './dist',
      templatesDir: config.templatesDir || './templates',
      port: config.port || 3000,
      plugins: config.plugins || [],
    };
  }

  use(plugin: Plugin): void {
    this.plugins.push(plugin);
  }

  private async loadPlugins(): Promise<void> {
    if (this.config.plugins) {
      for (const entry of this.config.plugins) {
        if (typeof entry === 'string') {
          try {
            const mod = require(entry);
            const plugin: Plugin = mod.default || mod;
            this.use(plugin);
          } catch {
            continue;
          }
        } else {
          this.use(entry);
        }
      }
    }
  }

  async loadFromConfig(configPath: string): Promise<void> {
    try {
      const mod = require(configPath);
      const externalConfig: SsgConfig = mod.default || mod;
      this.config = {
        ...this.config,
        ...externalConfig,
      };
      await this.loadPlugins();
    } catch {
      // Config file not found or invalid, use defaults
    }
  }

  async build(): Promise<Page[]> {
    await this.loadPlugins();

    const context: BuildContext = {
      config: this.config,
      pages: [],
      contentDir: this.config.contentDir,
      outputDir: this.config.outputDir,
      templatesDir: this.config.templatesDir,
      port: this.config.port,
    };

    for (const plugin of this.plugins) {
      if (plugin.onStart) {
        await plugin.onStart(context);
      }
    }

    for (const plugin of this.plugins) {
      if (plugin.beforeBuild) {
        await plugin.beforeBuild(context);
      }
    }

    for (const page of context.pages) {
      for (const plugin of this.plugins) {
        if (plugin.onFile) {
          await plugin.onFile(page, context);
        }
      }
    }

    for (const plugin of this.plugins) {
      if (plugin.afterBuild) {
        await plugin.afterBuild(context);
      }
    }

    for (const plugin of this.plugins) {
      if (plugin.onEnd) {
        await plugin.onEnd(context);
      }
    }

    return context.pages;
  }

  async serve(): Promise<void> {
    await this.loadPlugins();

    const context: BuildContext = {
      config: this.config,
      pages: [],
      contentDir: this.config.contentDir,
      outputDir: this.config.outputDir,
      templatesDir: this.config.templatesDir,
      port: this.config.port,
    };

    for (const plugin of this.plugins) {
      if (plugin.onStart) {
        await plugin.onStart(context);
      }
    }

    for (const plugin of this.plugins) {
      if (plugin.onEnd) {
        await plugin.onEnd(context);
      }
    }
  }
}
