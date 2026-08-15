import { Plugin, PluginContext } from '../plugin';
import { DevServer, DevServerOptions } from '../server';

export class DevServerPlugin implements Plugin {
  name = 'dev-server';

  private server: DevServer | null = null;
  private readonly options?: DevServerOptions;

  constructor(options?: DevServerOptions) {
    this.options = options;
  }

  onStart(context: PluginContext): void {
    const options: DevServerOptions = this.options ?? {
      contentDir: context.contentDir,
      outputDir: context.outputDir,
      templatesDir: context.templatesDir,
      port: typeof context.port === 'number' ? context.port : 3000,
      host: typeof context.host === 'string' ? context.host : undefined,
    };
    this.server = new DevServer(options);
    void this.server.start().catch((err) => {
      console.error(err instanceof Error ? err.message : String(err));
    });
  }

  onEnd(_context: PluginContext): void {
    void this.server?.stop();
    this.server = null;
  }

  getServer(): DevServer | null {
    return this.server;
  }
}
