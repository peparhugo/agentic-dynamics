import { createBuildContext, BuildOptions, Page, Plugin, resetOutput, runHook, writeIndex } from './plugin';
import { loadConfiguredPlugins } from './config';
import { MarkdownPlugin } from './plugins/markdown';
import { TemplatePlugin } from './plugins/template';

export { BuildOptions, Page } from './plugin';

export const builtInPlugins = (): Plugin[] => [new MarkdownPlugin(), new TemplatePlugin()];

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const context = createBuildContext(options);
  const plugins = [...builtInPlugins(), ...loadConfiguredPlugins(), ...(options.plugins ?? [])];
  await runHook(plugins, 'onStart', context);
  await resetOutput(context);
  await runHook(plugins, 'beforeBuild', context);
  for (const page of context.pages) await runHook(plugins, 'onFile', context, page);
  await writeIndex(context);
  await runHook(plugins, 'afterBuild', context);
  await runHook(plugins, 'onEnd', context);
  return context.pages;
}
