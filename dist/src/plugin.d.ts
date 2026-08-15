import { BuildOptions, Page } from './types';
import type { SsgEngine } from './engine';
import type { TemplateBundle } from './templates';
/**
 * Configuration loaded from `ssg.config.ts`.
 *
 * The `plugins` array lists additional plugin modules (resolved from the
 * `./plugins/` directory) or inline plugin instances that extend the site.
 */
export interface SsgConfig {
    plugins?: Array<string | Plugin>;
    [key: string]: unknown;
}
/**
 * Shared state threaded through every plugin hook invocation. The core engine
 * owns this context; plugins read options and can contribute rendered output
 * files or transform pages in place.
 */
export interface PluginContext {
    config: SsgConfig;
    options: BuildOptions;
    pages: Page[];
    outputFiles: Map<string, string>;
    templateBundle?: TemplateBundle;
    engine: SsgEngine;
}
/**
 * A plugin participating in the SSG lifecycle.
 *
 * Hooks run in registration order across every loaded plugin:
 *   - onStart()       called once when the engine begins
 *   - beforeBuild()   called before content is collected
 *   - onFile(page)    called for every content file, in file order
 *   - afterBuild()    called after every page has been processed
 *   - onEnd()         called once when the engine finishes
 */
export interface Plugin {
    name: string;
    onStart?(ctx: PluginContext): void | Promise<void>;
    beforeBuild?(ctx: PluginContext): void | Promise<void>;
    afterBuild?(ctx: PluginContext): void | Promise<void>;
    onFile?(page: Page, ctx: PluginContext): void | Promise<void>;
    onEnd?(ctx: PluginContext): void | Promise<void>;
}
export type PluginHook = 'onStart' | 'beforeBuild' | 'afterBuild' | 'onFile' | 'onEnd';
/**
 * Runs a lifecycle hook across all plugins in order, awaiting each hook to
 * completion before moving on to the next plugin.
 */
export declare class PluginPipeline {
    private readonly plugins;
    constructor(plugins: Plugin[]);
    getPlugins(): Plugin[];
    run(hook: PluginHook, ...args: unknown[]): Promise<void>;
}
