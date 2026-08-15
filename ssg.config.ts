import type { SsgConfig } from './src/plugin';

/**
 * Site configuration for the SSG.
 *
 * The `plugins` array can list plugin modules resolved from the `./plugins/`
 * directory (e.g. 'my-plugin') or inline plugin instances. The built-in
 * markdown and template plugins are always loaded automatically.
 */
const config: SsgConfig = {
  plugins: [],
};

export default config;
