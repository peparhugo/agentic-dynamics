import { BuildOptions, Page } from './ssg';

export interface PluginContext {
  options: BuildOptions;
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  pages: Page[];
  writtenFiles: string[];
  [key: string]: unknown;
}

export interface Plugin {
  name: string;
  onStart?(context: PluginContext): void | Promise<void>;
  beforeBuild?(context: PluginContext): void | Promise<void>;
  onFile?(page: Page, context: PluginContext): Page | void | Promise<Page | void>;
  afterBuild?(context: PluginContext): void | Promise<void>;
  onEnd?(context: PluginContext): void | Promise<void>;
}

type LifecycleHook = 'onStart' | 'beforeBuild' | 'afterBuild' | 'onEnd';

export function createPluginContext(options: BuildOptions): PluginContext {
  return {
    options,
    contentDir: options.contentDir,
    outputDir: options.outputDir,
    templatesDir: options.templatesDir ?? './templates',
    pages: [],
    writtenFiles: [],
  };
}

export function runSyncHooks(
  plugins: Plugin[],
  hook: LifecycleHook,
  context: PluginContext
): void {
  for (const plugin of plugins) {
    const fn = plugin[hook] as ((context: PluginContext) => void | Promise<void>) | undefined;
    if (fn) {
      fn.call(plugin, context);
    }
  }
}

export function runHooksAsync(
  plugins: Plugin[],
  hook: LifecycleHook,
  context: PluginContext
): Promise<void> {
  return plugins.reduce(
    (chain, plugin) =>
      chain.then(async () => {
        const fn = plugin[hook] as ((context: PluginContext) => void | Promise<void>) | undefined;
        if (fn) {
          await fn.call(plugin, context);
        }
      }),
    Promise.resolve()
  );
}

export function applyOnFile(plugins: Plugin[], page: Page, context: PluginContext): Page {
  let current = page;
  for (const plugin of plugins) {
    const fn = plugin.onFile as ((page: Page, context: PluginContext) => Page | void) | undefined;
    if (fn) {
      const result = fn.call(plugin, current, context);
      if (result != null) {
        current = result;
      }
    }
  }
  return current;
}

export function applyOnFileAsync(
  plugins: Plugin[],
  page: Page,
  context: PluginContext
): Promise<Page> {
  return plugins.reduce(
    (chain, plugin) =>
      chain.then(async (current) => {
        const fn = plugin.onFile;
        if (!fn) {
          return current;
        }
        const result = await fn.call(plugin, current, context);
        return result ?? current;
      }),
    Promise.resolve(page)
  );
}
