import type { BuildOptions, BuildStats, Page } from './types';
import type { Plugin } from './plugin';
export interface BuildInput extends BuildOptions {
    plugins?: Plugin[];
}
export interface BuildResult {
    pages: Page[];
    stats: BuildStats;
}
export declare function buildWithStats(options: BuildInput): Promise<BuildResult>;
export declare function build(options: BuildInput): Promise<Page[]>;
