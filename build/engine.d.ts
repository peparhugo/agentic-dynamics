import { Page } from './types';
import { Plugin, SSGOptions } from './plugin';
import { BuildStats } from './cache';
import { ServerInstance } from './plugins/devserver';
export declare class SSGEngine {
    private plugins;
    private context;
    private cache;
    constructor(options: SSGOptions);
    get pages(): Page[];
    get stats(): BuildStats | undefined;
    register(plugin: Plugin): void;
    build(): Promise<void>;
    serve(): Promise<ServerInstance>;
    shutdown(): Promise<void>;
    private runBuildPipeline;
    private runHook;
    private runOnFile;
}
//# sourceMappingURL=engine.d.ts.map