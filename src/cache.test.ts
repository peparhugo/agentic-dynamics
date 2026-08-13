import fs from 'fs';
import path from 'path';
import { BuildCache } from './cache';

const TEST_CACHE_DIR = path.join(__dirname, '__test-cache');
const TEST_CONTENT_DIR = path.join(__dirname, '__test-cache-content');

function setupTestDir(): void {
  if (fs.existsSync(TEST_CACHE_DIR)) {
    fs.rmSync(TEST_CACHE_DIR, { recursive: true });
  }
  fs.mkdirSync(TEST_CACHE_DIR, { recursive: true });

  if (fs.existsSync(TEST_CONTENT_DIR)) {
    fs.rmSync(TEST_CONTENT_DIR, { recursive: true });
  }
  fs.mkdirSync(TEST_CONTENT_DIR, { recursive: true });
}

function cleanupTestDir(): void {
  if (fs.existsSync(TEST_CACHE_DIR)) {
    fs.rmSync(TEST_CACHE_DIR, { recursive: true });
  }
  if (fs.existsSync(TEST_CONTENT_DIR)) {
    fs.rmSync(TEST_CONTENT_DIR, { recursive: true });
  }
}

describe('BuildCache', () => {
  beforeEach(setupTestDir);
  afterEach(cleanupTestDir);

  it('should create a new cache', () => {
    const cache = new BuildCache(TEST_CACHE_DIR);
    expect(cache).toBeDefined();
  });

  it('should load existing cache manifest', () => {
    const cacheFile = path.join(TEST_CACHE_DIR, '.ssg-cache.json');
    const manifest = {
      version: '1.0.0',
      entries: {
        'test.md': {
          fileHash: 'abc123',
          templateHash: 'def456',
          htmlHash: 'ghi789',
          frontmatterHash: 'jkl012',
          timestamp: Date.now(),
        },
      },
    };
    fs.writeFileSync(cacheFile, JSON.stringify(manifest), 'utf-8');

    const cache = new BuildCache(TEST_CACHE_DIR);
    const entry = cache.getCacheEntry('test.md');

    expect(entry).toBeDefined();
    expect(entry?.fileHash).toBe('abc123');
  });

  it('should compute file hash', () => {
    const filePath = path.join(TEST_CONTENT_DIR, 'test.md');
    fs.writeFileSync(filePath, 'content1');

    const cache = new BuildCache(TEST_CACHE_DIR);
    const hash1 = cache.getFileHash(filePath);

    fs.writeFileSync(filePath, 'content2');
    const hash2 = cache.getFileHash(filePath);

    expect(hash1).toBeDefined();
    expect(hash2).toBeDefined();
    expect(hash1).not.toBe(hash2);
  });

  it('should return null for non-existent file', () => {
    const cache = new BuildCache(TEST_CACHE_DIR);
    const hash = cache.getFileHash('/nonexistent/file.md');

    expect(hash).toBeNull();
  });

  it('should detect cache hit', () => {
    const filePath = 'test.md';
    const fileHash = 'abc123';
    const templateHash = 'def456';
    const html = '<p>content</p>';
    const frontmatter = '{"title":"Test"}';

    const cache = new BuildCache(TEST_CACHE_DIR);
    cache.setCacheEntry(filePath, fileHash, templateHash, html, frontmatter);

    const isCached = cache.isCached(filePath, null, fileHash, templateHash);
    expect(isCached).toBe(true);
  });

  it('should detect cache miss on file hash change', () => {
    const filePath = 'test.md';
    const fileHash = 'abc123';
    const newFileHash = 'xyz789';
    const templateHash = 'def456';
    const html = '<p>content</p>';
    const frontmatter = '{"title":"Test"}';

    const cache = new BuildCache(TEST_CACHE_DIR);
    cache.setCacheEntry(filePath, fileHash, templateHash, html, frontmatter);

    const isCached = cache.isCached(filePath, null, newFileHash, templateHash);
    expect(isCached).toBe(false);
  });

  it('should detect cache miss on template hash change', () => {
    const filePath = 'test.md';
    const fileHash = 'abc123';
    const templateHash = 'def456';
    const newTemplateHash = 'qqq999';
    const html = '<p>content</p>';
    const frontmatter = '{"title":"Test"}';

    const cache = new BuildCache(TEST_CACHE_DIR);
    cache.setCacheEntry(filePath, fileHash, templateHash, html, frontmatter);

    const isCached = cache.isCached(filePath, null, fileHash, newTemplateHash);
    expect(isCached).toBe(false);
  });

  it('should detect cache miss for uncached file', () => {
    const cache = new BuildCache(TEST_CACHE_DIR);
    const isCached = cache.isCached('uncached.md', null, 'abc123', 'def456');

    expect(isCached).toBe(false);
  });

  it('should invalidate cache entry', () => {
    const filePath = 'test.md';
    const fileHash = 'abc123';
    const templateHash = 'def456';
    const html = '<p>content</p>';
    const frontmatter = '{"title":"Test"}';

    const cache = new BuildCache(TEST_CACHE_DIR);
    cache.setCacheEntry(filePath, fileHash, templateHash, html, frontmatter);
    expect(cache.getCacheEntry(filePath)).toBeDefined();

    cache.invalidateCacheEntry(filePath);
    expect(cache.getCacheEntry(filePath)).toBeNull();
  });

  it('should save and load cache', () => {
    const filePath = 'test.md';
    const fileHash = 'abc123';
    const templateHash = 'def456';
    const html = '<p>content</p>';
    const frontmatter = '{"title":"Test"}';

    const cache1 = new BuildCache(TEST_CACHE_DIR);
    cache1.setCacheEntry(filePath, fileHash, templateHash, html, frontmatter);
    cache1.save();

    const cache2 = new BuildCache(TEST_CACHE_DIR);
    const entry = cache2.getCacheEntry(filePath);

    expect(entry).toBeDefined();
    expect(entry?.fileHash).toBe(fileHash);
    expect(entry?.templateHash).toBe(templateHash);
  });

  it('should clear all cache entries', () => {
    const cache = new BuildCache(TEST_CACHE_DIR);
    cache.setCacheEntry('test1.md', 'hash1', 'tmpl1', '<p>1</p>', '{}');
    cache.setCacheEntry('test2.md', 'hash2', 'tmpl2', '<p>2</p>', '{}');
    cache.save();

    cache.clear();

    expect(cache.getCacheEntry('test1.md')).toBeNull();
    expect(cache.getCacheEntry('test2.md')).toBeNull();
  });

  it('should track build start time', () => {
    const cache = new BuildCache(TEST_CACHE_DIR);
    const before = Date.now();
    cache.startBuild();
    const after = Date.now();

    const stats = cache.getStats(1, 0);
    expect(stats.pagesBuilt).toBe(1);
    expect(stats.pagesSkipped).toBe(0);
  });

  it('should calculate build stats correctly', () => {
    const cache = new BuildCache(TEST_CACHE_DIR);
    cache.startBuild();
    // Simulate some build time
    const start = Date.now();
    while (Date.now() - start < 10);

    const stats = cache.getStats(5, 3);
    expect(stats.pagesBuilt).toBe(5);
    expect(stats.pagesSkipped).toBe(3);
    expect(stats.timeSaved).toBeGreaterThanOrEqual(0);
  });

  it('should handle cache file parse errors gracefully', () => {
    const cacheFile = path.join(TEST_CACHE_DIR, '.ssg-cache.json');
    fs.writeFileSync(cacheFile, 'invalid json', 'utf-8');

    const cache = new BuildCache(TEST_CACHE_DIR);
    expect(cache).toBeDefined();
    expect(cache.getCacheEntry('test.md')).toBeNull();
  });
});
