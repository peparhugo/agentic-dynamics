import http from 'http';
import { Plugin, PluginContext } from '../plugin';
export interface ServerInstance {
    server: http.Server;
    close: () => Promise<void>;
    rebuild: () => void;
}
export declare class DevServerPlugin implements Plugin {
    name: string;
    private wss;
    private clients;
    private watcher;
    private rebuildTimer;
    private server;
    private rebuildCallback;
    onEnd(_context: PluginContext): void;
    startServer(context: PluginContext, rebuildFn: () => Promise<void>): Promise<ServerInstance>;
    private rebuild;
    private broadcastReload;
    private cleanup;
}
//# sourceMappingURL=devserver.d.ts.map