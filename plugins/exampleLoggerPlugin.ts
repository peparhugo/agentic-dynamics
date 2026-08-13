import { Page, Plugin, PluginContext } from '../src';

/**
 * Example user-authored plugin (the kind that lives in a project's
 * `./plugins/` directory and gets wired up via `ssg.config.ts`). Logs each
 * lifecycle stage as the build progresses.
 */
export function createLoggerPlugin(): Plugin {
  return {
    name: 'logger',
    onStart() {
      console.log('[logger] build starting');
    },
    beforeBuild(ctx: PluginContext) {
      console.log(`[logger] loaded ${ctx.pages.length} page(s)`);
    },
    onFile(page: Page) {
      console.log(`[logger] processed ${page.sourcePath}`);
    },
    afterBuild(ctx: PluginContext) {
      console.log(`[logger] wrote ${ctx.pages.length} page(s) to ${ctx.options.outputDir}`);
    },
    onEnd() {
      console.log('[logger] build complete');
    },
  };
}
