import { SSGOptions, BuildStats } from './types';
export interface BuildResult {
    stats: BuildStats;
}
export declare class SSGEngine {
    private plugins;
    private options;
    constructor(options: SSGOptions);
    private loadPlugins;
    private loadConfigPlugins;
    private tryLoadPlugin;
    private isPlugin;
    build(): BuildResult;
}
export declare function build(options: SSGOptions): BuildResult;
//# sourceMappingURL=ssg.d.ts.map