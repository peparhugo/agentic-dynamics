import * as path from 'path';
import { SsgEngine } from './engine';
import { MarkdownPlugin } from '../plugins/markdown';
import { TemplatePlugin } from '../plugins/template';
import type { Page } from './types';

export interface BuildOptions {
  contentDir: string;
  outputDir: string;
  /** Directory containing layouts/ and partials/ subdirectories. Defaults to ./templates relative to the current working directory. */
  templatesDir?: string;
}

export interface BuildResult {
  pages: Page[];
  outputDir: string;
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
  });

  return engine.build();
}
