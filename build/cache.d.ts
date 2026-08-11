import { Page } from './types';
export interface CachedPage {
    page: Page;
    html: string;
}
export interface CacheManifest {
    contentHashes: Record<string, string>;
    templateHash: string;
    pages: Record<string, CachedPage>;
    indexHtml?: string;
    indexSlugs?: string[];
}
export interface BuildStats {
    pagesBuilt: number;
    pagesSkipped: number;
    timeSavedMs?: number;
}
export declare class BuildCache {
    private data;
    private cachePath;
    constructor(cachePath: string);
    static computeHash(content: string): string;
    static computeFileHash(filePath: string): string;
    static computeTemplateHash(templateDir: string): string;
    load(): boolean;
    save(): void;
    clear(): void;
    isPopulated(): boolean;
    getContentHash(relPath: string): string | undefined;
    setContentHash(relPath: string, hash: string): void;
    getTemplateHash(): string;
    setTemplateHash(hash: string): void;
    getCachedPage(slug: string): CachedPage | undefined;
    setCachedPage(slug: string, cached: CachedPage): void;
    removeCachedPage(slug: string): void;
    getIndexHtml(): string | undefined;
    setIndexHtml(html: string): void;
    getIndexSlugs(): string[] | undefined;
    setIndexSlugs(slugs: string[]): void;
    removeContentHash(relPath: string): void;
    getCachedSlugs(): string[];
    getAllContentHashes(): Record<string, string>;
}
//# sourceMappingURL=cache.d.ts.map