import { Plugin, PluginContext } from '../plugin.js';
export interface DevServerOptions {
    port?: number;
    onRebuild?: () => Promise<void>;
}
export declare class DevServerPlugin implements Plugin {
    name: string;
    version: string;
    private httpServer;
    private wsServer;
    private options;
    private watcher;
    constructor(options?: DevServerOptions);
    onStart(context: PluginContext): Promise<void>;
    onEnd(context: PluginContext): Promise<void>;
    private setupHttpServer;
    private setupWatcher;
    private injectLiveReloadScript;
    private notifyClients;
    stop(): Promise<void>;
}
//# sourceMappingURL=dev-server-plugin.d.ts.map