import { BuildOptions, Page, BuildResult } from './types';
import { Plugin } from './plugin';
import { createEngine } from './engine';

export function build(options: BuildOptions, plugins: Plugin[] = []): Page[] {
  return createEngine(plugins).build(options);
}

export function buildIncremental(options: BuildOptions, plugins: Plugin[] = []): BuildResult {
  return createEngine(plugins).buildIncremental(options);
}
