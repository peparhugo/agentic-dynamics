import { Page, BuildOptions } from './types';
import { SSG } from './engine';
import { builtinPlugins } from './plugins';

export { collectPages } from './collect';

export function buildSite(options: BuildOptions): Page[] {
  const engine = new SSG({ options, plugins: builtinPlugins() });
  engine.start();
  return engine.build();
}
