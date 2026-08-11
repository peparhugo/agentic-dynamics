import { CacheEntry } from './types';
export declare function computeHash(content: string): string;
export declare function computeTemplateHash(templatesDir: string): string;
export declare class CacheManager {
    private manifestPath;
    private manifest;
    constructor(manifestPath: string);
    load(): void;
    save(): void;
    clear(): void;
    get(filePath: string, contentHash: string, templateHash: string): CacheEntry | null;
    set(filePath: string, contentHash: string, templateHash: string, html: string): void;
    updateTemplateHash(templateHash: string): void;
}
//# sourceMappingURL=cache.d.ts.map