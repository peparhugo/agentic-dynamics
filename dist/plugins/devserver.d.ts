import { Plugin, PluginContext } from '../src/plugin';
import type { DevServer } from '../src/serve';
/**
 * Built-in plugin implementing the live-reload development server.
 *
 * During `onStart` it performs an initial build, starts an HTTP server that
 * serves the built site, and watches the content and template directories. On
 * change it rebuilds through the core engine and tells connected browsers to
 * reload.
 */
export declare class DevServerPlugin implements Plugin {
    readonly name = "dev-server";
    private ctx;
    private server;
    private wss;
    private watcher;
    private port;
    private timer;
    private queue;
    onStart(ctx: PluginContext): Promise<void>;
    getServer(): DevServer;
    private setup;
    private broadcast;
    private rebuild;
    private close;
}
