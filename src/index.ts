import path from 'node:path';
import { loadPlugins } from './config';
import { MarkdownPlugin } from './plugins/markdown';
import { TemplatePlugin } from './plugins/template';
import { BuildContext, BuildOptions, Page, Plugin } from './types';

async function runHook(
  plugins: Plugin[],
  hook: 'onStart' | 'beforeBuild' | 'afterBuild' | 'onEnd',
  context: BuildContext
): Promise<void> {
  for (const plugin of plugins) await plugin[hook]?.(context);
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const context: BuildContext = {
    contentDir: path.resolve(options.contentDir ?? 'content'),
    outputDir: path.resolve(options.outputDir ?? 'dist'),
    templatesDir: path.resolve(options.templatesDir ?? 'templates'),
    pages: []
  };
  const plugins: Plugin[] = [new MarkdownPlugin(), new TemplatePlugin(), ...loadPlugins(options)];
  let buildError: unknown;

  try {
    await runHook(plugins, 'onStart', context);
    await runHook(plugins, 'beforeBuild', context);
    for (const page of context.pages) {
      for (const plugin of plugins) await plugin.onFile?.(page, context);
    }
    await runHook(plugins, 'afterBuild', context);
    return context.pages;
  } catch (error) {
    buildError = error;
    throw error;
  } finally {
    try {
      await runHook(plugins, 'onEnd', context);
    } catch (error) {
      if (buildError === undefined) throw error;
    }
  }
}

export { MarkdownPlugin } from './plugins/markdown';
export { TemplatePlugin } from './plugins/template';
export { DevServerPlugin } from './plugins/dev-server';
export type { BuildContext, BuildOptions, Page, Plugin, SsgConfig } from './types';
