import { BuildOptions, Page } from './types';
import { Plugin } from './plugin';
import { createEngine } from './engine';

export function build(options: BuildOptions, plugins: Plugin[] = []): Page[] {
  return createEngine(plugins).build(options);
}
