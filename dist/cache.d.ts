import type { Frontmatter } from './frontmatter';
export interface CachedPage {
    slug: string;
    title: string;
    date?: string;
    tags: string[];
    contentHtml: string;
    sourcePath: string;
    outputPath: string;
    template?: string;
    layout?: string;
    data: Frontmatter;
    content?: string;
    html?: string;
    sourceHash: string;
    templateHash: string;
    buildTimeMs: number;
}
export interface CacheManifest {
    version: number;
    templatesHash: string;
    pages: Record<string, CachedPage>;
}
export declare const CACHE_VERSION = 1;
export declare const CACHE_FILENAME = ".ssg-cache.json";
export declare function hashString(input: string): string;
export declare function hashFile(filePath: string): Promise<string>;
export declare function computeTemplatesHash(templatesDir: string): Promise<string>;
export declare class CacheManager {
    private readonly cachePath;
    constructor(outputDir: string);
    load(): Promise<CacheManifest | undefined>;
    save(manifest: CacheManifest): Promise<void>;
    clear(): Promise<void>;
}
