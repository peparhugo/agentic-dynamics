import fs from 'fs';
import path from 'path';
import { Plugin, BuildContext, SSGConfig } from './plugin';
import { SSGOptions, BuildStats } from './types';
import { MarkdownPlugin } from './plugins/markdown-plugin';
import { TemplatePlugin } from './plugins/template-plugin';
import { CacheManager, BuildStats as CacheStats } from './cache';

export interface BuildResult {
  stats: BuildStats;
}

export class SSGEngine {
  private plugins: Plugin[] = [];
  private options: SSGOptions;

  constructor(options: SSGOptions) {
    this.options = options;
    this.loadPlugins();
  }

  private loadPlugins(): void {
    this.plugins.push(new MarkdownPlugin());
    this.plugins.push(new TemplatePlugin());

    this.loadConfigPlugins();
  }

  private loadConfigPlugins(): void {
    const configDirs = [process.cwd(), __dirname, path.resolve('.')];
    const configNames = ['ssg.config.js', 'ssg.config.ts'];

    for (const dir of configDirs) {
      for (const name of configNames) {
        const configPath = path.join(dir, name);
        if (fs.existsSync(configPath)) {
          try {
            const cfg = require(configPath);
            const config: SSGConfig = cfg.default || cfg;
            if (config.plugins) {
              for (const entry of config.plugins) {
                if (typeof entry === 'string') {
                  const plugin = this.tryLoadPlugin(entry);
                  if (plugin && !this.plugins.some(p => p.name === plugin.name)) {
                    this.plugins.push(plugin);
                  }
                }
              }
            }
          } catch {
            // Config loading is best-effort
          }
          return;
        }
      }
    }
  }

  private tryLoadPlugin(name: string): Plugin | null {
    const builtinMap: Record<string, Plugin> = {
      'markdown': new MarkdownPlugin(),
      'template': new TemplatePlugin(),
    };

    if (builtinMap[name]) {
      return builtinMap[name];
    }

    try {
      const mod = require(path.resolve(name));
      const PluginClass = mod.default || mod[name + 'Plugin'] || mod;
      if (typeof PluginClass === 'function') {
        const instance = new PluginClass();
        if (this.isPlugin(instance)) {
          return instance;
        }
      }
      return null;
    } catch {
      return null;
    }
  }

  private isPlugin(obj: any): obj is Plugin {
    return obj && typeof obj.name === 'string' && (
      typeof obj.onStart === 'function' ||
      typeof obj.beforeBuild === 'function' ||
      typeof obj.onFile === 'function' ||
      typeof obj.afterBuild === 'function' ||
      typeof obj.onEnd === 'function'
    );
  }

  build(): BuildResult {
    const { outputDir, incremental, clean } = this.options;

    if (!fs.existsSync(outputDir)) {
      fs.mkdirSync(outputDir, { recursive: true });
    }

    const context: BuildContext = {
      options: this.options,
      pages: [],
      outputDir,
    };

    let cache: CacheManager | null = null;

    if (incremental) {
      cache = new CacheManager(path.join(outputDir, '.ssg-cache.json'));
      if (clean) {
        cache.delete();
      }
      cache.load();
      const templatesHash = cache.computeTemplatesHash(this.options.templateDir || '');
      const manifest = cache.getManifest();
      const templatesChanged = !manifest || manifest.templatesHash !== templatesHash;
      context.cache = cache;
      context.templatesChanged = templatesChanged;
      context.incremental = true;
    }

    for (const plugin of this.plugins) {
      if (plugin.onStart) {
        plugin.onStart(context);
      }
    }

    for (const plugin of this.plugins) {
      if (plugin.beforeBuild) {
        plugin.beforeBuild(context);
      }
    }

    for (const page of context.pages) {
      const isCached = incremental && !!(page as any)._fromCache;
      if (isCached) {
        if (cache) {
          cache.incrementSkipped();
        }
      }

      for (const plugin of this.plugins) {
        if (plugin.onFile) {
          plugin.onFile(page, context);
        }
      }
    }

    for (const plugin of this.plugins) {
      if (plugin.afterBuild) {
        plugin.afterBuild(context);
      }
    }

    if (incremental && cache) {
      const templatesHash = cache.currentTemplatesHash;
      const newManifest = cache.buildManifest(templatesHash);
      if (Object.keys(newManifest.pages).length > 0) {
        cache.save(newManifest);
      }
    }

    for (const plugin of this.plugins) {
      if (plugin.onEnd) {
        plugin.onEnd(context);
      }
    }

    const stats: BuildStats = cache
      ? cache.getStats()
      : { pagesBuilt: context.pages.length, pagesSkipped: 0 };

    if (incremental) {
      console.log(`Build complete: ${stats.pagesBuilt} page(s) built, ${stats.pagesSkipped} page(s) skipped`);
    }

    return { stats };
  }
}

export function build(options: SSGOptions): BuildResult {
  const engine = new SSGEngine(options);
  return engine.build();
}
