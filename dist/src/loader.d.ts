import { Plugin, SsgConfig } from './plugin';
export declare const PLUGIN_DIR = "plugins";
/**
 * Build the plugin list. Built-in plugins (markdown, templates) are always
 * registered first; plugins configured in `ssg.config.ts` are appended in
 * order, so every hook runs across all of them sequentially.
 */
export declare function loadPlugins(config: SsgConfig): Promise<Plugin[]>;
