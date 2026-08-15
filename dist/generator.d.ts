import { BuildOptions } from './types.js';
import { PluginManager } from './plugin-manager.js';
import { Plugin } from './plugin.js';
import { CacheManager } from './cache-manager.js';
export interface BuildStats {
    pagesBuilt: number;
    pagesSkipped: number;
    totalTime: number;
    timeSaved: number;
}
export declare class SiteGenerator {
    private contentDir;
    private outputDir;
    private templatesDir;
    private pluginManager;
    private cacheManager;
    private incremental;
    private clean;
    private buildStats;
    constructor(options: BuildOptions, plugins?: Plugin[]);
    private ensureDir;
    private getMarkdownFiles;
    private generateIndexHtml;
    private escapeHtml;
    getPluginManager(): PluginManager;
    getCacheManager(): CacheManager;
    getBuildStats(): BuildStats;
    build(): Promise<void>;
    private shouldRebuildFile;
    private getTemplateFromContent;
    private getLayoutFromContent;
    private getTemplatePath;
    private getLayoutPath;
    private reconstructMetadata;
    private reportBuildStats;
}
//# sourceMappingURL=generator.d.ts.map