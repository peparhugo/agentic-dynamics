import http from "http";
import { WebSocketServer } from "ws";
export interface DevServerOptions {
    contentDir: string;
    outputDir: string;
    templatesDir?: string;
    port: number;
}
export declare function injectLiveReloadScript(html: string, port: number): string;
export declare function startDevServer(options: DevServerOptions): Promise<{
    server: http.Server;
    wss: WebSocketServer;
    close: () => Promise<void>;
}>;
