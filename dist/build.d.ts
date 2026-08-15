import type { BuildOptions, Page } from './types';
import type { Plugin } from './plugin';
export interface BuildInput extends BuildOptions {
    plugins?: Plugin[];
}
export declare function build(options: BuildInput): Promise<Page[]>;
