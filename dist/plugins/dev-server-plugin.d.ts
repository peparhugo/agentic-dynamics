import http from 'http';
import { WebSocketServer } from 'ws';
import { FSWatcher } from 'chokidar';
import { Plugin } from '../plugin';
import { SSGEngine } from '../ssg';
export interface DevServerOptions {
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
export declare class DevServerPlugin implements Plugin {
    name: string;
    private engine;
    private instance;
    setEngine(engine: SSGEngine): void;
    start(options: DevServerOptions): ServeInstance;
    getInstance(): ServeInstance | null;
}
//# sourceMappingURL=dev-server-plugin.d.ts.map