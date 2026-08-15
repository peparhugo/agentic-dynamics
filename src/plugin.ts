import path from 'node:path';
import { Frontmatter } from './parser';

export interface Page {
  source: string;
  url: string;
  data: Frontmatter;
  content: string;
  html: string;
  body: string;
  rendered?: string;
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
  defaultTemplate?: string;
  configFile?: string;
  plugins?: Plugin[];
  incremental?: boolean;
  clean?: boolean;
}

export interface PluginContext {
  options: Required<Pick<BuildOptions, 'contentDir' | 'outputDir' | 'templatesDir' | 'defaultTemplate'>>;
  pages: Page[];
  files: string[];
  state: Map<string, unknown>;
  rebuild: () => Promise<void>;
}

export interface Plugin {
  onStart?(context: PluginContext): void | Promise<void>;
  beforeBuild?(context: PluginContext): void | Promise<void>;
  onFile?(page: Page, context: PluginContext): void | Promise<void>;
  afterBuild?(context: PluginContext): void | Promise<void>;
  onEnd?(context: PluginContext): void | Promise<void>;
}

export function resolveBuildOptions(options: BuildOptions): PluginContext['options'] {
  return {
    contentDir: path.resolve(options.contentDir ?? './content'),
    outputDir: path.resolve(options.outputDir ?? './dist'),
    templatesDir: path.resolve(options.templatesDir ?? './templates'),
    defaultTemplate: options.defaultTemplate ?? 'default',
  };
}
