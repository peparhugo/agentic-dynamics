import { BuildOptions, Page } from './types';
export type HookResult = void | Promise<void>;
export type LifecycleHook = 'onStart' | 'beforeBuild' | 'afterBuild' | 'onEnd';
export interface Plugin {
    name: string;
    onStart?(): HookResult;
    beforeBuild?(): HookResult;
    afterBuild?(): HookResult;
    onFile?(page: Page): HookResult;
    onEnd?(): HookResult;
}
export interface PluginContext {
    options: BuildOptions;
    contentDir: string;
    outputDir: string;
    templatesDir: string;
    pages: Page[];
}
/**
 * Runs each lifecycle hook across all plugins in registration order.
 */
export declare class PluginPipeline {
    readonly plugins: Plugin[];
    constructor(plugins: Plugin[]);
    runSync(hook: LifecycleHook): void;
    runFileSync(page: Page): void;
    run(hook: LifecycleHook): Promise<void>;
    runFile(page: Page): Promise<void>;
}
