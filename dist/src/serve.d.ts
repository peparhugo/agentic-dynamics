import type { Server } from 'http';
import type { WebSocketServer } from 'ws';
import { BuildOptions } from './types';
export { injectReloadScript, reloadClientScript } from './livereload';
export interface ServeOptions extends BuildOptions {
    port?: number;
}
export interface DevServer {
    server: Server;
    wss: WebSocketServer;
    port: number;
    close(): Promise<void>;
}
/**
 * Start a live-reload development server.
 *
 * Delegates to the core SSG engine with the dev-server plugin loaded, which
 * performs an initial build, serves the built site from `outputDir`, watches
 * `contentDir` and `templatesDir` for changes, rebuilds on change, and tells
 * connected browsers to reload once a rebuild finishes.
 */
export declare function startDevServer(options: ServeOptions): Promise<DevServer>;
