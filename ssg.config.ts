/**
 * SSG configuration.
 *
 * The `plugins` array lists plugins to load, in execution order, after the
 * built-in markdown and template plugins. Each entry can be:
 *   - a built-in plugin name ('markdown', 'templates', 'dev-server')
 *   - a relative path to a TypeScript plugin module under `./plugins/`
 *   - a Plugin object or factory function
 */

import examplePlugin from './plugins/example';

export default {
  plugins: [examplePlugin],
};
