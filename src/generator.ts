import type { Plugin } from './plugin';
import { createPluginContext } from './plugin';
import { MarkdownPlugin, parsePages } from './plugins/markdown';
import { TemplatePlugin } from './plugins/template';
import { loadPlugins } from './config';

export interface Page {
  slug: string;
  title: string;
  date?: string;
  tags: string[];
  html: string;
  template?: string;
  layout?: string;
  data: Record<string, unknown>;
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
  plugins?: Plugin[];
}

type Hook = 'onStart' | 'beforeBuild' | 'afterBuild' | 'onEnd';

async function runHook(plugins: Plugin[], hook: Hook, context: ReturnType<typeof createPluginContext>): Promise<void> {
  for (const plugin of plugins) await plugin[hook]?.(context);
}

export async function readPages(contentDir: string): Promise<Page[]> {
  return parsePages(contentDir);
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const context = createPluginContext(options);
  const configuredPlugins = options.plugins ?? await loadPlugins();
  const plugins = [new MarkdownPlugin(), new TemplatePlugin(), ...configuredPlugins];
  await runHook(plugins, 'onStart', context);
  try {
    await runHook(plugins, 'beforeBuild', context);
    for (const page of context.pages) {
      for (const plugin of plugins) await plugin.onFile?.(page, context);
    }
    await runHook(plugins, 'afterBuild', context);
    return context.pages;
  } finally {
    await runHook(plugins, 'onEnd', context);
  }
}
