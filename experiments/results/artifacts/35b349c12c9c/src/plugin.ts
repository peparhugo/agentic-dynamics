import path from 'path';

import type { BuildResult, BuildOptions, Page } from './site-generator';

export interface PluginContext {
  options: Required<BuildOptions>;
  pages: Page[];
  result?: BuildResult;
}

export interface Plugin {
  onStart?(context: PluginContext): void | Promise<void>;
  beforeBuild?(context: PluginContext): void | Promise<void>;
  afterBuild?(context: PluginContext): void | Promise<void>;
  onFile?(page: Page, context: PluginContext): Page | void | Promise<Page | void>;
  onEnd?(context: PluginContext): void | Promise<void>;
}

export type PluginModule = Plugin | (() => Plugin) | { default?: Plugin | (() => Plugin); plugins?: Plugin[] };

export function resolveBuildOptions(options: BuildOptions): Required<BuildOptions> {
  return {
    contentDir: path.resolve(options.contentDir ?? './content'),
    outputDir: path.resolve(options.outputDir ?? './dist'),
    templatesDir: path.resolve(options.templatesDir ?? './templates'),
    defaultTemplate: options.defaultTemplate ?? 'default',
    configFile: options.configFile ?? 'ssg.config.ts',
    plugins: options.plugins ?? [],
  };
}
