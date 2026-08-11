import { Page, Frontmatter } from './types';
export interface CachePageEntry {
    sourceHash: string;
    templateName: string;
    layoutName: string;
    frontmatter: Frontmatter;
    html: string;
    renderedHTML: string;
}
export interface CacheManifest {
    pages: Record<string, CachePageEntry>;
    templatesHash: string;
}
export interface BuildStats {
    pagesBuilt: number;
    pagesSkipped: number;
}
export declare class CacheManager {
    private manifest;
    private cachePath;
    private htmlCache;
    private pageCache;
    private frontmatterCache;
    private _pageEntries;
    private _pagesBuilt;
    private _pagesSkipped;
    private _currentTemplatesHash;
    constructor(cachePath: string);
    get pagesBuilt(): number;
    get pagesSkipped(): number;
    get currentTemplatesHash(): string;
    incrementBuilt(): void;
    incrementSkipped(): void;
    getStats(): BuildStats;
    load(): CacheManifest | null;
    getManifest(): CacheManifest | null;
    save(newManifest?: CacheManifest): void;
    delete(): void;
    setPageEntry(slug: string, sourceHash: string, templateName: string, layoutName: string): void;
    buildManifest(templatesHash: string): CacheManifest;
    computeFileHash(filePath: string): string;
    computeTemplatesHash(templateDir: string): string;
    private hashDirectory;
    isPageDirty(slug: string, sourceHash: string, templateName: string, layoutName: string, templatesChanged: boolean): boolean;
    getCachedPage(slug: string): Page | undefined;
    setCachedPage(slug: string, page: Page): void;
    getCachedHTML(slug: string): string | undefined;
    setCachedHTML(slug: string, html: string): void;
    getCachedFrontmatter(slug: string): Frontmatter | undefined;
    setCachedFrontmatter(slug: string, fm: Frontmatter): void;
}
//# sourceMappingURL=cache.d.ts.map