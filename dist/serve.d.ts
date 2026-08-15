import { Server } from 'http';
import { WebSocketServer } from 'ws';
import { BuildOptions } from './types';
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
 * Browser-side client that connects to the live-reload WebSocket endpoint and
 * reloads the page when a `reload` message arrives.
 */
export declare function reloadClientScript(): string;
/**
 * Inject the live-reload client script into an HTML document just before the
 * closing `</body>` tag.
 */
export declare function injectReloadScript(html: string): string;
/**
 * Start a live-reload development server.
 *
 * Performs an initial build, serves the built site from `outputDir`, watches
 * `contentDir` and `templatesDir` for changes, rebuilds on change, and tells
 * connected browsers to reload once a rebuild finishes.
 */
export declare function startDevServer(options: ServeOptions): Promise<DevServer>;
