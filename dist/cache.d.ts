export declare const CACHE_FILENAME = ".ssg-cache.json";
export declare const CACHE_VERSION = 1;
/**
 * A single cached page. It captures every field the build pipeline produces so
 * that an unchanged page can be reconstructed without re-running the plugins.
 */
export interface CachedPage {
    slug: string;
    /** SHA-256 digest of the raw Markdown source file. */
    sourceHash: string;
    /** SHA-256 digest of the layout + partials the page resolves to. */
    templateHash: string;
    title: string;
    date?: string;
    tags: string[];
    template?: string;
    /** Stripped Markdown body (frontmatter removed). */
    content: string;
    /** Rendered body HTML. */
    html: string;
    /** Final full-page HTML written to disk. */
    rendered: string;
}
export interface CacheManifest {
    version: number;
    pages: Record<string, CachedPage>;
}
/** Returns the default location of the manifest within the output directory. */
export declare function defaultCacheFile(outputDir: string): string;
/** Loads the manifest from disk, returning an empty one when missing/corrupt. */
export declare function loadManifest(cacheFile: string): CacheManifest;
/** Persists the manifest to disk. */
export declare function saveManifest(cacheFile: string, manifest: CacheManifest): void;
