import { BuildOptions, BuildStats, Page } from './types';
/**
 * Build a static site from Markdown content.
 *
 * Delegates to the core SSG engine, which orchestrates the plugin pipeline
 * (markdown parsing, template rendering, and any configured plugins).
 */
export declare function build(options: BuildOptions): Promise<Page[]>;
export interface BuildResult {
    pages: Page[];
    stats: BuildStats;
}
/**
 * Build a static site and return the generated pages together with the build
 * statistics (pages built, skipped, and time saved by incremental caching).
 */
export declare function buildWithStats(options: BuildOptions): Promise<BuildResult>;
