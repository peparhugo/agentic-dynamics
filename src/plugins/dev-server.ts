import chokidar, { FSWatcher } from 'chokidar';
import { WebSocket, WebSocketServer } from 'ws';
import { Plugin, PluginContext } from '../plugin';

export class DevServerPlugin implements Plugin {
  name = 'dev-server';

  readonly wss: WebSocketServer = new WebSocketServer({ noServer: true });
  watcher: FSWatcher | null = null;

  private rebuildFn: (() => void) | null = null;
  private readyResolve!: () => void;
  private readyReject!: (err: Error) => void;
  private readonly readyPromise: Promise<void>;

  constructor() {
    this.readyPromise = new Promise<void>((resolve, reject) => {
      this.readyResolve = resolve;
      this.readyReject = reject;
    });
  }

  setRebuild(fn: () => void): void {
    this.rebuildFn = fn;
  }

  onStart(context: PluginContext): void {
    this.watcher = chokidar.watch([context.contentDir, context.templatesDir], { ignoreInitial: true });
    this.watcher.on('change', this.rebuild);
    this.watcher.on('add', this.rebuild);
    this.watcher.on('unlink', this.rebuild);
    this.watcher.on('addDir', this.rebuild);
    this.watcher.on('unlinkDir', this.rebuild);
    this.watcher.on('ready', () => this.readyResolve());
    this.watcher.on('error', (err: Error) => this.readyReject(err));
  }

  ready(): Promise<void> {
    return this.readyPromise;
  }

  close(): Promise<void> {
    if (!this.watcher) return Promise.resolve();
    return this.watcher.close();
  }

  private readonly rebuild = (): void => {
    try {
      if (this.rebuildFn) this.rebuildFn();
      this.notifyClients();
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      process.stderr.write(`Rebuild error: ${message}\n`);
    }
  };

  private notifyClients(): void {
    for (const client of this.wss.clients) {
      if (client.readyState === WebSocket.OPEN) {
        try {
          client.send('reload');
        } catch {
          // client may have closed between the readyState check and send
        }
      }
    }
  }
}
