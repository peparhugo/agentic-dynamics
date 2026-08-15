export interface CacheEntry {
    filename: string;
    fileHash: string;
    templateHash?: string;
    layoutHash?: string;
    html?: string;
    title?: string;
    date?: string;
    tags?: string[];
    timestamp: number;
}
export interface CacheManifest {
    version: string;
    entries: Record<string, CacheEntry>;
}
export declare class CacheManager {
    private cacheFile;
    private manifest;
    constructor(outputDir: string);
    private loadManifest;
    private hashContent;
    saveManifest(): void;
    getEntry(filename: string): CacheEntry | undefined;
    setEntry(filename: string, entry: CacheEntry): void;
    hasEntry(filename: string): boolean;
    removeEntry(filename: string): void;
    isFileChanged(filename: string, fileContent: string, templatePath?: string, layoutPath?: string): boolean;
    updateEntry(filename: string, fileContent: string, html: string, templatePath?: string, layoutPath?: string, metadata?: {
        title?: string;
        date?: string;
        tags?: string[];
    }): void;
    clear(): void;
    getEntries(): CacheEntry[];
    getAllFilenames(): string[];
}
//# sourceMappingURL=cache-manager.d.ts.map