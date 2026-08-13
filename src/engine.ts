import { Plugin, PluginContext } from './plugin';
import { BuildOptions, BuildResult, Page } from './types';

type StageHook = 'onStart' | 'beforeBuild' | 'afterBuild' | 'onEnd';

function isThenable(value: unknown): value is Promise<unknown> {
  return !!value && typeof (value as { then?: unknown }).then === 'function';
}

/**
 * Orchestrates a build across a list of Plugins. For each stage, every
 * plugin's hook for that stage runs in list order before the next stage
 * begins; `onFile` runs the full plugin chain once per page (in list
 * order) so a plugin can transform a page before a later plugin persists
 * it.
 *
 * `runSync` powers `buildSite()` and requires every hook to complete
 * synchronously (it throws if a plugin returns a Promise); use `run` for
 * pipelines that include async plugins (e.g. DevServerPlugin).
 */
export class SSGEngine {
  constructor(private readonly plugins: Plugin[]) {}

  runSync(options: BuildOptions): BuildResult {
    const ctx: PluginContext = { options, pages: [] };

    this.runStageSync('onStart', ctx);
    this.runStageSync('beforeBuild', ctx);
    ctx.pages = ctx.pages.map((page) => this.runFileHooksSync(page, ctx));
    this.runStageSync('afterBuild', ctx);
    this.runStageSync('onEnd', ctx);

    return { pages: ctx.pages, outputDir: options.outputDir };
  }

  async run(options: BuildOptions): Promise<BuildResult> {
    const ctx: PluginContext = { options, pages: [] };

    await this.runStage('onStart', ctx);
    await this.runStage('beforeBuild', ctx);

    const pages: Page[] = [];
    for (const page of ctx.pages) {
      pages.push(await this.runFileHooks(page, ctx));
    }
    ctx.pages = pages;

    await this.runStage('afterBuild', ctx);
    await this.runStage('onEnd', ctx);

    return { pages: ctx.pages, outputDir: options.outputDir };
  }

  private runStageSync(hook: StageHook, ctx: PluginContext): void {
    for (const plugin of this.plugins) {
      const result = plugin[hook]?.(ctx);
      if (isThenable(result)) {
        throw new Error(
          `Plugin "${plugin.name}" returned a Promise from ${hook}(); use SSGEngine.run() for async plugin pipelines.`
        );
      }
    }
  }

  private runFileHooksSync(page: Page, ctx: PluginContext): Page {
    let current = page;
    for (const plugin of this.plugins) {
      const result = plugin.onFile?.(current, ctx);
      if (isThenable(result)) {
        throw new Error(
          `Plugin "${plugin.name}" returned a Promise from onFile(); use SSGEngine.run() for async plugin pipelines.`
        );
      }
      if (result) current = result;
    }
    return current;
  }

  private async runStage(hook: StageHook, ctx: PluginContext): Promise<void> {
    for (const plugin of this.plugins) {
      await plugin[hook]?.(ctx);
    }
  }

  private async runFileHooks(page: Page, ctx: PluginContext): Promise<Page> {
    let current = page;
    for (const plugin of this.plugins) {
      const result = await plugin.onFile?.(current, ctx);
      if (result) current = result;
    }
    return current;
  }
}
