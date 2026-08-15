import type { BuildOptions, Page } from './types';
import type { SsgConfig } from './config';
export interface PluginContext {
    options: BuildOptions;
    config: SsgConfig;
    cwd: string;
    [key: string]: unknown;
}
export interface Plugin {
    name: string;
    onStart?(context: PluginContext): void | Promise<void>;
    beforeBuild?(context: PluginContext): void | Promise<void>;
    onFile?(page: Page, context: PluginContext): Page | void | Promise<Page | void>;
    afterBuild?(pages: Page[], context: PluginContext): void | Promise<void>;
    onEnd?(context: PluginContext): void | Promise<void>;
}
export declare function isPlugin(value: unknown): value is Plugin;
