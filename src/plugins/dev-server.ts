import type { Plugin } from '../plugin';
import type { RunningServer, ServeOptions } from '../server';

/** Built-in integration point for development serving and live reload. */
export class DevServerPlugin implements Plugin {
  name = 'dev-server';
  private running?: RunningServer;

  constructor(private readonly options: ServeOptions = {}) {}

  async start(): Promise<RunningServer> {
    const { startServer } = await import('../server');
    this.running = await startServer(this.options);
    return this.running;
  }

  async stop(): Promise<void> {
    await this.running?.close();
    this.running = undefined;
  }
}
