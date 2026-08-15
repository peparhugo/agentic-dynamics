export interface PageData {
  slug: string;
  filename: string;
  content: string;
  metadata: Record<string, any>;
}

export interface BuildContext {
  contentDir: string;
  outputDir: string;
  templatesDir?: string;
  layoutsDir?: string;
  partialsDir?: string;
  pages: PageData[];
  cacheManager?: any;
  incremental?: boolean;
  pagesBuilt: number;
  pagesSkipped: number;
  [key: string]: any;
}

export interface Plugin {
  name: string;
  onStart?(context: BuildContext): Promise<void>;
  beforeBuild?(context: BuildContext): Promise<void>;
  onFile?(page: PageData, context: BuildContext): Promise<void>;
  afterBuild?(context: BuildContext): Promise<void>;
  onEnd?(context: BuildContext): Promise<void>;
}

export class PluginManager {
  private plugins: Plugin[] = [];

  addPlugin(plugin: Plugin): void {
    this.plugins.push(plugin);
  }

  async callHook(hookName: keyof Plugin, context: BuildContext, page?: PageData): Promise<void> {
    for (const plugin of this.plugins) {
      const hook = plugin[hookName];
      if (typeof hook === 'function') {
        if (hookName === 'onFile' && page) {
          await (hook as (page: PageData, context: BuildContext) => Promise<void>)(page, context);
        } else {
          await (hook as (context: BuildContext) => Promise<void>)(context);
        }
      }
    }
  }

  getPlugins(): Plugin[] {
    return this.plugins;
  }
}
