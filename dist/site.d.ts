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
}
export interface BuildResult {
    posts: Post[];
    filesWritten: string[];
    outputDir: string;
}
/**
 * Build a static site by running the plugin pipeline.
 *
 * The built-in `MarkdownPlugin` and `TemplatePlugin` always run first (in that
 * order), followed by any plugins passed via `options.plugins` and any plugins
 * declared in the project's `ssg.config.ts`.
 */
export declare function buildSite(options: BuildOptions): BuildResult;
