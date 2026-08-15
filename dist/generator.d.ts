import { BuildOptions } from './types.js';
import { PluginManager } from './plugin-manager.js';
import { Plugin } from './plugin.js';
export declare class SiteGenerator {
    private contentDir;
    private outputDir;
    private templatesDir;
    private pluginManager;
    constructor(options: BuildOptions, plugins?: Plugin[]);
    private ensureDir;
    private getMarkdownFiles;
    private generateIndexHtml;
    private escapeHtml;
    getPluginManager(): PluginManager;
    build(): Promise<void>;
}
//# sourceMappingURL=generator.d.ts.map