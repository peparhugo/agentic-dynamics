import { Plugin } from '../plugin';
import { ServeHandle, ServeOptions, startServer } from '../serve';

/**
 * Built-in plugin that starts the development server.
 *
 * `onStart` builds the site, serves it over HTTP and begins watching the
 * content/templates directories for changes. `onEnd` tears the server down.
 */
export class DevServerPlugin implements Plugin {
  name = 'dev-server';

  private handle?: ServeHandle;

  constructor(private options: ServeOptions = {}) {}

  async onStart(): Promise<void> {
    this.handle = await startServer(this.options);
  }

  async onEnd(): Promise<void> {
    if (this.handle) {
      await this.handle.close();
      this.handle = undefined;
    }
  }

  get address(): string | undefined {
    return this.handle?.address;
  }

  get port(): number | undefined {
    return this.handle?.port;
  }
}
