export interface CacheEntry {
    hash: string;
    templateHash?: string;
    timestamp: number;
}
export interface CacheData {
    version: number;
    entries: Record<string, CacheEntry>;
}
export interface BuildStats {
    pagesBuilt: number;
    pagesSkipped: number;
    timeSaved: number;
}
export declare class CacheManager {
    private cachePath;
    private cacheData;
    private buildStartTime;
    constructor(outputDir: string);
    private loadCache;
    private computeHash;
    private getFileHash;
    hasChanged(fileKey: string, content: string, templatePath?: string): boolean;
    updateEntry(fileKey: string, content: string, templatePath?: string): void;
    save(): void;
    clear(): void;
    getStats(pagesBuilt: number, pagesSkipped: number): BuildStats;
}
//# sourceMappingURL=cache.d.ts.map