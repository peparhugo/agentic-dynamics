import http from 'http';
import { WebSocketServer } from 'ws';
import { FSWatcher } from 'chokidar';
export interface ServeOptions {
    contentDir: string;
    outputDir: string;
    templateDir?: string;
    port: number;
}
export interface ServeInstance {
    server: http.Server;
    watcher: FSWatcher;
    wss: WebSocketServer;
}
export declare function serve(options: ServeOptions): ServeInstance;
//# sourceMappingURL=serve.d.ts.map