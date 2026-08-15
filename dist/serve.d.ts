import http from 'http';
import { FSWatcher } from 'chokidar';
import { WebSocketServer } from 'ws';
export interface ServeOptions {
    content?: string;
    output?: string;
    templates?: string;
    port?: number;
    host?: string;
}
export interface ServeHandle {
    server: http.Server;
    wss: WebSocketServer;
    watcher: FSWatcher;
    port: number;
    host: string;
    address: string;
    outputDir: string;
    close: () => Promise<void>;
    rebuild: () => void;
}
export declare const LIVE_RELOAD_PATH = "/__ssg_livereload";
export declare function injectLiveReloadScript(html: string): string;
export declare function startServer(options?: ServeOptions): Promise<ServeHandle>;
