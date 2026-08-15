import { Post } from './types';
/**
 * A page flowing through the plugin pipeline.
 *
 * The core engine reads each Markdown file and creates an initial `Page` whose
 * `content` field still holds the raw source (including frontmatter). The
 * built-in `MarkdownPlugin` parses it and rewrites `content` to the stripped
 * Markdown body while filling in the metadata and `html`. The built-in
 * `TemplatePlugin` then renders the final full-page HTML into `rendered`.
 */
export interface Page extends Post {
    /**
     * The final, full-page HTML produced by the template plugin. The engine
     * writes this value to disk. It is not part of the public `Post` type
     * returned by `buildSite`.
     */
    rendered?: string;
}
export type MaybePromise<T> = T | Promise<T>;
/**
 * The lifecycle of a plugin. Each hook is optional.
 *
 * - `onStart()`      runs once before anything else.
 * - `beforeBuild()`  runs once after `onStart` and before any page is read.
 * - `onFile(page)`   runs once per page, in pipeline order.
 * - `afterBuild()`   runs once after every page has been processed and written.
 * - `onEnd()`        runs once at the very end of the build.
 */
export interface Plugin {
    name?: string;
    onStart?(): MaybePromise<void>;
    beforeBuild?(): MaybePromise<void>;
    onFile?(page: Page): MaybePromise<void>;
    afterBuild?(): MaybePromise<void>;
    onEnd?(): MaybePromise<void>;
}
/**
 * Runs every plugin's hook for a given lifecycle stage, preserving plugin
 * order. Hooks may be synchronous or return a Promise.
 */
export declare class PluginPipeline {
    readonly plugins: Plugin[];
    constructor(plugins?: Plugin[]);
    onStart(): Promise<void>;
    beforeBuild(): Promise<void>;
    onFile(page: Page): Promise<void>;
    afterBuild(): Promise<void>;
    onEnd(): Promise<void>;
}
