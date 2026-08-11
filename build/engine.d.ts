import { Page } from './types';
import { Plugin, SSGOptions } from './plugin';
import { ServerInstance } from './plugins/devserver';
export declare class SSGEngine {
    private plugins;
    private context;
    constructor(options: SSGOptions);
    get pages(): Page[];
    register(plugin: Plugin): void;
    build(): Promise<void>;
    serve(): Promise<ServerInstance>;
    shutdown(): Promise<void>;
    private runBuildPipeline;
    private runHook;
    private runOnFile;
}
//# sourceMappingURL=engine.d.ts.map