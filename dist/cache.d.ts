import { Page } from './plugin';
export interface ManifestEntry {
    hash: string;
    slug: string;
    lastBuilt: number;
}
export interface CacheManifest {
    templates?: string;
    pages: Record<string, ManifestEntry>;
}
export interface BuildStats {
    totalPages: number;
    pagesBuilt: number;
    pagesSkipped: number;
    timeSaved: string;
}
declare function hashContent(content: string): string;
declare function hashFile(filePath: string): string;
declare function hashTemplatesDir(templatesDir: string): string;
export declare class BuildCache {
    private contentDir;
    private outputDir;
    private templatesDir?;
    private manifestPath;
    private manifest;
    private inMemoryHtmlCache;
    private inMemoryFmCache;
    private _currentTplHash;
    private _currentTplHashComputed;
    stats: BuildStats;
    constructor(contentDir: string, outputDir: string, templatesDir?: string);
    load(): void;
    hasValidManifest(): boolean;
    clear(): void;
    private currentTemplateHash;
    shouldSkipFile(sourcePath: string, slug: string): boolean;
    updateManifest(sourcePath: string, slug: string): void;
    finalize(): void;
    getCurrentTemplateHash(): string;
    removeStaleEntries(knownSlugs: Set<string>): void;
    persist(): void;
    cacheHtml(slug: string, html: string): void;
    getCachedHtml(slug: string): string | undefined;
    cacheFrontmatter(slug: string, page: Page): void;
    getCachedFrontmatter(slug: string): Page | undefined;
    computeSourceHash(sourcePath: string): string;
    reportStats(consoleLog?: boolean): void;
}
export { hashFile, hashContent, hashTemplatesDir as hashDirectoryTemplates };
//# sourceMappingURL=cache.d.ts.map