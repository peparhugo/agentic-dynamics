import fs from 'fs';
import path from 'path';
import type { Page } from './types';
import type {
  Plugin,
  PluginContext,
  PluginEngine,
  PluginFactory,
  SSGConfig,
} from './plugins/types';

export type EngineCommand = 'build' | 'serve';

export interface EngineOptions {
  contentDir: string;
  outputDir: string;
  templateDir?: string;
  defaultTemplate?: string;
  defaultLayout?: string;
  command?: EngineCommand;
  config?: SSGConfig;
}

type HookName = 'onStart' | 'beforeBuild' | 'afterBuild' | 'onEnd';

function isPromise(value: unknown): value is Promise<unknown> {
  return (
    value !== null &&
    typeof value === 'object' &&
    typeof (value as { then?: unknown }).then === 'function'
  );
}

/**
 * The core SSG engine. Owns the shared plugin context and orchestrates the
 * plugin pipeline. Hooks run in plugin registration order:
 *
 *   onStart -> beforeBuild -> onFile (per content file) -> afterBuild -> onEnd
 *
 * The pipeline is available both synchronously (`buildSync`/`runSync`) for
 * the CLI build command and asynchronously (`build`/`run`) so plugins can
 * perform async work in long-running sessions such as the dev server.
 */
export class SsgEngine implements PluginEngine {
  readonly plugins: Plugin[];
  readonly context: PluginContext;

  private readonly contentDir: string;
  private readonly outputDir: string;

  constructor(options: EngineOptions, plugins: Array<Plugin | PluginFactory>) {
    this.contentDir = path.resolve(options.contentDir);
    this.outputDir = path.resolve(options.outputDir);
    const context: PluginContext = {
      command: options.command ?? 'build',
      config: options.config ?? {},
      contentDir: this.contentDir,
      outputDir: this.outputDir,
      templateDir: options.templateDir,
      defaultTemplate: options.defaultTemplate,
      defaultLayout: options.defaultLayout,
      pages: [],
      plugins: [],
      shared: {},
      engine: this,
    };
    const resolved: Plugin[] = [];
    for (const entry of plugins) {
      const plugin = typeof entry === 'function' ? entry(context) : entry;
      resolved.push(plugin);
    }
    context.plugins = resolved;
    this.plugins = resolved;
    this.context = context;
  }

  /** Run the `onStart` hooks. */
  async start(): Promise<void> {
    await this.runHook('onStart');
  }

  /** Run the `onEnd` hooks. */
  async end(): Promise<void> {
    await this.runHook('onEnd');
  }

  /** Run the full build pipeline and return the generated pages. */
  async build(): Promise<Page[]> {
    this.validateContentDir();
    await this.runHook('beforeBuild');
    fs.mkdirSync(this.outputDir, { recursive: true });
    const pages = await this.collectPages();
    this.context.pages = pages;
    await this.runHook('afterBuild');
    return pages;
  }

  /** Run the entire lifecycle: onStart, build, onEnd. */
  async run(): Promise<Page[]> {
    await this.start();
    const pages = await this.build();
    await this.end();
    return pages;
  }

  /** Synchronous build pipeline (all hooks must return synchronously). */
  buildSync(): Page[] {
    this.validateContentDir();
    this.runHookSync('beforeBuild');
    fs.mkdirSync(this.outputDir, { recursive: true });
    const pages = this.collectPagesSync();
    this.context.pages = pages;
    this.runHookSync('afterBuild');
    return pages;
  }

  /** Synchronous full lifecycle: onStart, build, onEnd. */
  runSync(): Page[] {
    this.runHookSync('onStart');
    const pages = this.buildSync();
    this.runHookSync('onEnd');
    return pages;
  }

  private validateContentDir(): void {
    if (!fs.existsSync(this.contentDir)) {
      throw new Error(`Content directory does not exist: ${this.contentDir}`);
    }
    if (!fs.statSync(this.contentDir).isDirectory()) {
      throw new Error(`Content path is not a directory: ${this.contentDir}`);
    }
  }

  private async runHook(name: HookName): Promise<void> {
    for (const plugin of this.plugins) {
      const hook = plugin[name];
      if (!hook) {
        continue;
      }
      await hook.call(plugin, this.context);
    }
  }

  private runHookSync(name: HookName): void {
    for (const plugin of this.plugins) {
      const hook = plugin[name];
      if (!hook) {
        continue;
      }
      const result = hook.call(plugin, this.context);
      if (isPromise(result)) {
        throw new Error(
          `Plugin "${plugin.name}" returned a Promise from "${name}" during a synchronous build`
        );
      }
    }
  }

  private async collectPages(): Promise<Page[]> {
    const pages: Page[] = [];
    const entries = fs.readdirSync(this.contentDir).sort();
    for (const entry of entries) {
      const page = await this.runOnFile(entry);
      if (page) {
        pages.push(page);
      }
    }
    return pages;
  }

  private collectPagesSync(): Page[] {
    const pages: Page[] = [];
    const entries = fs.readdirSync(this.contentDir).sort();
    for (const entry of entries) {
      const page = this.runOnFileSync(entry);
      if (page) {
        pages.push(page);
      }
    }
    return pages;
  }

  private async runOnFile(entry: string): Promise<Page | null> {
    let page: Page | null | undefined = { slug: entry, title: entry, contentHtml: '', content: '' };
    for (const plugin of this.plugins) {
      if (!plugin.onFile) {
        continue;
      }
      const result = await plugin.onFile(page, this.context);
      if (result === undefined || result === null) {
        page = null;
        break;
      }
      page = result;
    }
    return page;
  }

  private runOnFileSync(entry: string): Page | null {
    let page: Page | null | undefined = { slug: entry, title: entry, contentHtml: '', content: '' };
    for (const plugin of this.plugins) {
      if (!plugin.onFile) {
        continue;
      }
      const result = plugin.onFile(page, this.context);
      if (isPromise(result)) {
        throw new Error(
          `Plugin "${plugin.name}" returned a Promise from "onFile" during a synchronous build`
        );
      }
      if (result === undefined || result === null) {
        page = null;
        break;
      }
      page = result;
    }
    return page;
  }
}
