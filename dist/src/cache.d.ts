export interface CacheEntry {
    sourceHash: string;
    templatesHash: string;
    outputHtml: string;
    title: string;
    date?: string;
    tags?: string[];
    template?: string;
    layout?: string;
}
export interface SsgCacheManifest {
    version: number;
    pages: Record<string, CacheEntry>;
    templatesHash: string;
}
export interface BuildStats {
    pagesBuilt: number;
    pagesSkipped: number;
}
export declare function hashContent(content: string): string;
export declare function hashFile(filePath: string): string;
export declare function computeTemplatesHash(templatesDir: string): string;
export declare function loadCache(cachePath: string): SsgCacheManifest | null;
export declare function saveCache(cachePath: string, manifest: SsgCacheManifest): void;
export declare function removeCache(cachePath: string): void;
export declare function createEmptyManifest(): SsgCacheManifest;
//# sourceMappingURL=cache.d.ts.map