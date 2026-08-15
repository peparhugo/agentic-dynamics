import { BuildOptions } from './types.js';
export declare class SiteGenerator {
    private contentDir;
    private outputDir;
    private templatesDir;
    private templateEngine;
    constructor(options: BuildOptions);
    private ensureDir;
    private getMarkdownFiles;
    private renderPageWithTemplate;
    private generatePageHtml;
    private generateIndexHtml;
    private escapeHtml;
    build(): Promise<void>;
}
//# sourceMappingURL=generator.d.ts.map