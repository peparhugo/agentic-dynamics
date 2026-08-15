import { Plugin } from './plugin';
/**
 * The shape of a `ssg.config.ts` file. It may export the config directly, as a
 * `default` export, or as a function returning the config.
 */
export interface SsgConfig {
    plugins?: Plugin[];
}
/**
 * Registers a `require` extension for `.ts` files so that `ssg.config.ts` and
 * its plugin modules (which live in `./plugins/*.ts`) can be loaded at runtime.
 * No-op when TypeScript support is already registered (ts-node, ts-jest, ...).
 */
export declare function installTypeScriptRequireHook(): void;
/**
 * Loads and evaluates a `ssg.config.ts` (or `.js`/`.mjs`/`.cjs`) file from the
 * given directory, returning the exported configuration object.
 */
export declare function loadConfig(dir?: string): SsgConfig;
/**
 * Loads the plugin instances declared in the `ssg.config.ts` file located in
 * the given directory.
 */
export declare function loadPlugins(dir?: string): Plugin[];
