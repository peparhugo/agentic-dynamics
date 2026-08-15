import * as path from 'path';
import { SsgEngine } from './engine';
import { MarkdownPlugin } from '../plugins/markdown';
import { TemplatePlugin } from '../plugins/template';
import type { BuildStats } from './engine';
import type { Page } from './types';

export interface BuildOptions {
  contentDir: string;
  outputDir: string;
  /** Directory containing layouts/ and partials/ subdirectories. Defaults to ./templates relative to the current working directory. */
  templatesDir?: string;
  /** When true, pages whose source file and the templates directory are unchanged since the last cached build reuse their cached result instead of re-running the plugin pipeline. */
  incremental?: boolean;
  /** Forces a full rebuild: any existing cache manifest is discarded before the build runs. */
  clean?: boolean;
  /** Path to the incremental build cache manifest. Defaults to `.ssg-cache.json` inside outputDir. */
  cacheFile?: string;
}

export interface BuildResult {
  pages: Page[];
  outputDir: string;
  stats: BuildStats;
}

/** The default (non-plugin-configured) build pipeline: parse Markdown, then render it through templates. */
export function defaultBuildPlugins(): [MarkdownPlugin, TemplatePlugin] {
  return [new MarkdownPlugin(), new TemplatePlugin()];
}

export function build(options: BuildOptions): BuildResult {
  const { contentDir, outputDir } = options;
  const templatesDir = options.templatesDir ?? path.resolve(process.cwd(), 'templates');

  const engine = new SsgEngine({
    contentDir,
    outputDir,
    templatesDir,
    plugins: defaultBuildPlugins(),
    incremental: options.incremental,
    clean: options.clean,
    cacheFile: options.cacheFile,
  });

  return engine.build();
}
