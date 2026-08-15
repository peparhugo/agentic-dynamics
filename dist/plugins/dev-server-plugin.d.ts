import { Plugin, BuildContext } from '../plugin.js';
export interface DevServerPluginOptions {
    port?: number;
    onRebuild?: () => Promise<void>;
    test?: boolean;
}
export declare class DevServerPlugin implements Plugin {
    name: string;
    private port;
    private server;
    private wss;
    private watcher;
    private clients;
    private isRebuilding;
    private onRebuild?;
    private test;
    constructor(options?: DevServerPluginOptions);
    onStart(context: BuildContext): Promise<void>;
    onEnd(context: BuildContext): Promise<void>;
}
//# sourceMappingURL=dev-server-plugin.d.ts.map