import type { BuildOptions, Page } from './types';
import type { Plugin } from './plugin';
import type { SsgConfig } from './config';
import { MarkdownPlugin } from './plugins/markdown';
import { TemplatePlugin } from './plugins/template';
export interface EngineOptions extends BuildOptions {
    plugins?: Plugin[];
}
export declare class SsgEngine {
    readonly options: EngineOptions;
    readonly config: SsgConfig;
    readonly plugins: Plugin[];
    readonly markdown: MarkdownPlugin;
    readonly template: TemplatePlugin;
    private readonly context;
    private pages;
    constructor(options: EngineOptions, config: SsgConfig, plugins: Plugin[]);
    get builtPages(): Page[];
    run(): Promise<Page[]>;
}
