import { Plugin } from './plugin';
export interface SSGConfig {
    contentDir?: string;
    outputDir?: string;
    templateDir?: string;
    plugins?: Plugin[];
}
export declare function setConfig(newConfig: Partial<SSGConfig>): void;
export declare function getConfig(): SSGConfig;
export declare function loadConfigFile(configPath: string): Promise<SSGConfig>;
//# sourceMappingURL=config.d.ts.map