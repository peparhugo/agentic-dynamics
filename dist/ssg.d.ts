import { Plugin, SsgConfig } from './plugin';
import { Page } from './types';
export declare class SSG {
    private config;
    private plugins;
    constructor(config: SsgConfig);
    use(plugin: Plugin): void;
    private loadPlugins;
    loadFromConfig(configPath: string): Promise<void>;
    build(): Promise<Page[]>;
    serve(): Promise<void>;
}
//# sourceMappingURL=ssg.d.ts.map