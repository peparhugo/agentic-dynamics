import type { Plugin } from './plugin';
export interface SsgConfig {
    plugins?: Array<Plugin | string>;
}
export declare function defineConfig(config: SsgConfig): SsgConfig;
export declare function normalizeConfig(raw: unknown): SsgConfig;
export declare function loadConfig(cwd?: string): Promise<SsgConfig>;
export declare function loadConfigFile(filePath: string): Promise<SsgConfig>;
export declare function resolvePlugins(entries: Array<Plugin | string> | undefined, baseDir: string): Promise<Plugin[]>;
