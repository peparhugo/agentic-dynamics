import { Page } from './types';
/**
 * Incremental build cache.
 *
 * A `.ssg-cache.json` manifest records, for every page slug, the hash of the
 * raw source content, the hash of the templates used to render it, and the
 * previously computed page data / rendered HTML. On an incremental build a
 * page is only re-parsed and re-rendered when its source or its templates
 * changed; otherwise the cached output is reused.
 */
export declare const CACHE_VERSION = 1;
export declare const DEFAULT_CACHE_FILE = ".ssg-cache.json";
export interface CacheEntry {
    sourceHash: string;
    templateHash: string;
    /** Parsed page data (frontmatter + rendered markdown body). */
    page: Page | null;
    /** Final rendered HTML output for the page. */
    html: string | null;
    /** Wall-clock ms spent rendering this page on its last build. */
    renderMs: number;
}
export interface CacheManifest {
    version: number;
    files: Record<string, CacheEntry>;
}
export declare function hashContent(content: string): string;
/**
 * The cache lives on disk as a JSON manifest, but a fresh instance with an
 * empty manifest is returned whenever the file is missing, unreadable, or
 * written by an incompatible version so builds never fail on a stale cache.
 */
export declare class SsgCache {
    private readonly manifest;
    private readonly cacheFilePath;
    constructor(cacheFilePath: string, manifest?: CacheManifest);
    static load(cacheFilePath: string): Promise<SsgCache>;
    get(key: string): CacheEntry | undefined;
    set(key: string, entry: CacheEntry): void;
    get entries(): Record<string, CacheEntry>;
    save(): Promise<void>;
}
/** Deep-copy the page fields the markdown plugin produces. */
export declare function snapshotPage(page: Page): Page;
/** Copy parsed page fields from `source` onto `target` in place. */
export declare function applyParsedPage(source: Page, target: Page): void;
