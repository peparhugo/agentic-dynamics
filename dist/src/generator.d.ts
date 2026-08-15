import { BuildOptions, Page } from './types';
/**
 * Build a static site from Markdown content.
 *
 * Delegates to the core SSG engine, which orchestrates the plugin pipeline
 * (markdown parsing, template rendering, and any configured plugins).
 */
export declare function build(options: BuildOptions): Promise<Page[]>;
