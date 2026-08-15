import { Plugin } from './plugin';
import { Post } from './types';
export interface BuildOptions {
    contentDir: string;
    outputDir: string;
    templatesDir?: string;
    /** Extra plugins appended after the built-in plugins. */
    plugins?: Plugin[];
    /** Directory searched for `ssg.config.ts`. Defaults to `process.cwd()`. */
    configDir?: string;
    /** Rebuild only pages whose source or template changed. */
    incremental?: boolean;
    /** Ignore any existing cache and force a full rebuild. */
    clean?: boolean;
    /** Override the location of the `.ssg-cache.json` manifest. */
    cacheFile?: string;
}
export interface BuildStats {
    /** Number of pages that ran the full plugin pipeline. */
    pagesBuilt: number;
    /** Number of pages reused from the cache. */
    pagesSkipped: number;
    /** Estimated time saved by skipping unchanged pages, in milliseconds. */
    timeSavedMs: number;
}
export interface BuildResult {
    posts: Post[];
    filesWritten: string[];
    outputDir: string;
    stats?: BuildStats;
}
/**
 * Build a static site by running the plugin pipeline.
 *
 * The built-in `MarkdownPlugin` and `TemplatePlugin` always run first (in that
 * order), followed by any plugins passed via `options.plugins` and any plugins
 * declared in the project's `ssg.config.ts`.
 */
export declare function buildSite(options: BuildOptions): BuildResult;
