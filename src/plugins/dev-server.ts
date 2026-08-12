import type { Plugin } from '../plugin';
import type { ServeOptions, DevServer } from '../server';

/** Built-in development-server plugin. The public server entry point owns startup. */
export class DevServerPlugin implements Plugin {
  constructor(public readonly options: ServeOptions = {}) {}

  start(): Promise<DevServer> {
    // Loaded lazily to avoid coupling normal builds to the HTTP server lifecycle.
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const { startDevServer } = require('../server') as typeof import('../server');
    return startDevServer(this.options);
  }
}
