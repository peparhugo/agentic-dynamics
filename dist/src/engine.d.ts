import { Plugin, PluginContext, SsgConfig } from './plugin';
import { BuildOptions, Page } from './types';
/**
 * Core SSG engine.
 *
 * Owns the plugin pipeline and orchestrates the lifecycle hooks:
 * `onStart` -> `beforeBuild` -> `onFile` (per content file) -> `afterBuild`
 * -> write outputs -> `onEnd`. Plugins transform pages and contribute output
 * files; the engine is responsible for discovery, ordering, and writing.
 */
export declare class SsgEngine {
    private readonly pipeline;
    private readonly context;
    constructor(plugins: Plugin[], options: BuildOptions, config?: SsgConfig);
    getContext(): PluginContext;
    /**
     * Run a full build lifecycle (used by the `build` command).
     */
    build(): Promise<Page[]>;
    /**
     * Rebuild content without running start/end hooks (used by the dev server
     * to refresh the site on file changes).
     */
    rebuild(): Promise<Page[]>;
    private collectPages;
    /**
     * Run the serve lifecycle. The dev-server plugin starts the server during
     * `onStart`; the resulting server handle is returned to the caller.
     */
    serve(): Promise<unknown>;
    private collectContent;
    private writeOutputs;
}
