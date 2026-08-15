import type { AddressInfo } from 'net';
import { LiveReloadDevServer } from '../dev-server';
import type { DevServerOptions } from '../dev-server';
import type { Plugin, PluginContext, PluginEngine } from './types';

/**
 * Built-in dev-server plugin: runs the live-reload development server for the
 * `serve` command. It performs the initial build through the plugin pipeline
 * and re-runs that pipeline on every file change so the site is rebuilt the
 * same way as a plain `build`.
 */
export class DevServerPlugin implements Plugin {
  readonly name = 'dev-server';

  private server: LiveReloadDevServer | null = null;
  private context: PluginContext | null = null;

  onStart(context: PluginContext): void {
    this.context = context;
  }

  onEnd(context: PluginContext): void {
    this.context = context;
  }

  /** The running dev server, once `start` has completed. */
  getServer(): LiveReloadDevServer | null {
    return this.server;
  }

  /**
   * Start the dev server and wait until it is listening. Uses an ephemeral
   * port when `port` is 0. An initial build is performed through the engine
   * so the output directory is up to date before serving begins.
   */
  start(engine: PluginEngine, options: DevServerOptions): Promise<LiveReloadDevServer> {
    const rebuild = (): boolean => {
      try {
        engine.buildSync();
        return true;
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        console.error(`Rebuild failed: ${message}`);
        return false;
      }
    };

    const devServer = new LiveReloadDevServer({ ...options, rebuild });

    let initialBuildError: unknown;
    try {
      engine.buildSync();
    } catch (error) {
      initialBuildError = error;
    }

    if (initialBuildError !== undefined) {
      devServer.watcher.close().catch(() => undefined);
      return Promise.reject(initialBuildError);
    }

    return new Promise<LiveReloadDevServer>((resolve, reject) => {
      const listening = new Promise<void>((resolveListen, rejectListen) => {
        devServer.server.once('error', rejectListen);
        devServer.server.once('listening', () => {
          devServer.server.removeListener('error', rejectListen);
          const address = devServer.server.address() as AddressInfo | null;
          if (address && typeof address === 'object') {
            devServer.port = address.port;
          }
          resolveListen();
        });
        devServer.server.listen(devServer.port);
      });
      const watcherReady = new Promise<void>((resolveReady) => {
        devServer.watcher.once('ready', () => resolveReady());
      });

      Promise.all([listening, watcherReady])
        .then(() => {
          this.server = devServer;
          resolve(devServer);
        })
        .catch((error) => {
          devServer.watcher.close().catch(() => undefined);
          reject(error);
        });
    });
  }
}
