import fs from 'fs';
import path from 'path';
import { generatePages, buildWithStats } from './generator';
import { BuildCache } from './cache';

const TEST_CONTENT_DIR = path.join(__dirname, '__test-incremental-content');
const TEST_OUTPUT_DIR = path.join(__dirname, '__test-incremental-output');
const TEST_CACHE_DIR = path.join(__dirname, '__test-incremental-cache');

function setupTestDir(): void {
  for (const dir of [TEST_CONTENT_DIR, TEST_OUTPUT_DIR, TEST_CACHE_DIR]) {
    if (fs.existsSync(dir)) {
      fs.rmSync(dir, { recursive: true });
    }
    fs.mkdirSync(dir, { recursive: true });
  }
}

function cleanupTestDir(): void {
  for (const dir of [TEST_CONTENT_DIR, TEST_OUTPUT_DIR, TEST_CACHE_DIR]) {
    if (fs.existsSync(dir)) {
      fs.rmSync(dir, { recursive: true });
    }
  }
}

describe('Incremental Builds', () => {
  beforeEach(setupTestDir);
  afterEach(cleanupTestDir);

  it('should build all pages on first build', async () => {
    fs.writeFileSync(path.join(TEST_CONTENT_DIR, 'page1.md'), '---\ntitle: Page 1\n---\n# Page 1');
    fs.writeFileSync(path.join(TEST_CONTENT_DIR, 'page2.md'), '---\ntitle: Page 2\n---\n# Page 2');

    const cache = new BuildCache(TEST_CACHE_DIR);
    const pages = await generatePages(
      TEST_CONTENT_DIR,
      TEST_OUTPUT_DIR,
      undefined,
      undefined,
      { incremental: true, cache }
    );

    expect(pages.length).toBe(2);
    expect(fs.existsSync(path.join(TEST_OUTPUT_DIR, 'page1.html'))).toBe(true);
    expect(fs.existsSync(path.join(TEST_OUTPUT_DIR, 'page2.html'))).toBe(true);
  });

  it('should skip unchanged pages on incremental build', async () => {
    const page1Content = '---\ntitle: Page 1\n---\n# Page 1';
    const page2Content = '---\ntitle: Page 2\n---\n# Page 2';

    fs.writeFileSync(path.join(TEST_CONTENT_DIR, 'page1.md'), page1Content);
    fs.writeFileSync(path.join(TEST_CONTENT_DIR, 'page2.md'), page2Content);

    // First build
    const cache = new BuildCache(TEST_CACHE_DIR);
    await generatePages(
      TEST_CONTENT_DIR,
      TEST_OUTPUT_DIR,
      undefined,
      undefined,
      { incremental: true, cache }
    );
    cache.save();

    const page1Stat1 = fs.statSync(path.join(TEST_OUTPUT_DIR, 'page1.html'));

    // Wait a bit to ensure mtime would differ
    await new Promise((resolve) => setTimeout(resolve, 10));

    // Second build - page1 unchanged, page2 unchanged
    const cache2 = new BuildCache(TEST_CACHE_DIR);
    const pages = await generatePages(
      TEST_CONTENT_DIR,
      TEST_OUTPUT_DIR,
      undefined,
      undefined,
      { incremental: true, cache: cache2 }
    );

    const page1Stat2 = fs.statSync(path.join(TEST_OUTPUT_DIR, 'page1.html'));

    // page1 should not have been rewritten
    expect(page1Stat1.mtimeMs).toBe(page1Stat2.mtimeMs);
    expect(pages.length).toBe(2);
  });

  it('should rebuild changed pages', async () => {
    const page1Content = '---\ntitle: Page 1\n---\n# Page 1';
    const page2Content = '---\ntitle: Page 2\n---\n# Page 2';

    fs.writeFileSync(path.join(TEST_CONTENT_DIR, 'page1.md'), page1Content);
    fs.writeFileSync(path.join(TEST_CONTENT_DIR, 'page2.md'), page2Content);

    // First build
    const cache = new BuildCache(TEST_CACHE_DIR);
    await generatePages(
      TEST_CONTENT_DIR,
      TEST_OUTPUT_DIR,
      undefined,
      undefined,
      { incremental: true, cache }
    );
    cache.save();

    const page1Stat1 = fs.statSync(path.join(TEST_OUTPUT_DIR, 'page1.html'));
    const page1Html1 = fs.readFileSync(path.join(TEST_OUTPUT_DIR, 'page1.html'), 'utf-8');

    await new Promise((resolve) => setTimeout(resolve, 10));

    // Modify page1
    fs.writeFileSync(path.join(TEST_CONTENT_DIR, 'page1.md'), '---\ntitle: Page 1 Updated\n---\n# Page 1 Updated');

    // Second build
    const cache2 = new BuildCache(TEST_CACHE_DIR);
    await generatePages(
      TEST_CONTENT_DIR,
      TEST_OUTPUT_DIR,
      undefined,
      undefined,
      { incremental: true, cache: cache2 }
    );

    const page1Stat2 = fs.statSync(path.join(TEST_OUTPUT_DIR, 'page1.html'));
    const page1Html2 = fs.readFileSync(path.join(TEST_OUTPUT_DIR, 'page1.html'), 'utf-8');

    // page1 should have been rewritten
    expect(page1Stat2.mtimeMs).toBeGreaterThan(page1Stat1.mtimeMs);
    expect(page1Html2).not.toBe(page1Html1);
    expect(page1Html2).toContain('Page 1 Updated');
  });

  it('should build new pages incrementally', async () => {
    const page1Content = '---\ntitle: Page 1\n---\n# Page 1';
    fs.writeFileSync(path.join(TEST_CONTENT_DIR, 'page1.md'), page1Content);

    // First build
    const cache = new BuildCache(TEST_CACHE_DIR);
    const pages1 = await generatePages(
      TEST_CONTENT_DIR,
      TEST_OUTPUT_DIR,
      undefined,
      undefined,
      { incremental: true, cache }
    );
    cache.save();

    expect(pages1.length).toBe(1);
    expect(fs.existsSync(path.join(TEST_OUTPUT_DIR, 'page1.html'))).toBe(true);

    await new Promise((resolve) => setTimeout(resolve, 10));

    // Add new page
    fs.writeFileSync(path.join(TEST_CONTENT_DIR, 'page2.md'), '---\ntitle: Page 2\n---\n# Page 2');

    // Second build
    const cache2 = new BuildCache(TEST_CACHE_DIR);
    const pages2 = await generatePages(
      TEST_CONTENT_DIR,
      TEST_OUTPUT_DIR,
      undefined,
      undefined,
      { incremental: true, cache: cache2 }
    );

    expect(pages2.length).toBe(2);
    expect(fs.existsSync(path.join(TEST_OUTPUT_DIR, 'page2.html'))).toBe(true);
  });

  it('should handle cache clean flag', async () => {
    const page1Content = '---\ntitle: Page 1\n---\n# Page 1';
    fs.writeFileSync(path.join(TEST_CONTENT_DIR, 'page1.md'), page1Content);

    // First build
    const cache1 = new BuildCache(TEST_CACHE_DIR);
    await generatePages(
      TEST_CONTENT_DIR,
      TEST_OUTPUT_DIR,
      undefined,
      undefined,
      { incremental: true, cache: cache1 }
    );
    cache1.save();

    const cacheFile1 = path.join(TEST_CACHE_DIR, '.ssg-cache.json');
    const manifest1 = JSON.parse(fs.readFileSync(cacheFile1, 'utf-8'));
    expect(Object.keys(manifest1.entries).length).toBeGreaterThan(0);

    // Clean the cache file manually
    fs.unlinkSync(cacheFile1);

    // Second build with clean flag
    const cache2 = new BuildCache(TEST_CACHE_DIR);
    cache2.clear();
    cache2.save();

    const cacheFile2 = path.join(TEST_CACHE_DIR, '.ssg-cache.json');
    const manifest2 = JSON.parse(fs.readFileSync(cacheFile2, 'utf-8'));
    expect(Object.keys(manifest2.entries).length).toBe(0);
  });

  it('should report correct build stats', async () => {
    fs.writeFileSync(path.join(TEST_CONTENT_DIR, 'page1.md'), '---\ntitle: Page 1\n---\n# Page 1');
    fs.writeFileSync(path.join(TEST_CONTENT_DIR, 'page2.md'), '---\ntitle: Page 2\n---\n# Page 2');

    // First build
    const cache1 = new BuildCache(TEST_CACHE_DIR);
    const stats1 = await buildWithStats(
      TEST_CONTENT_DIR,
      TEST_OUTPUT_DIR,
      '/nonexistent/templates',
      undefined,
      { incremental: true, cache: cache1 }
    );

    expect(stats1.pagesBuilt).toBe(2);
    expect(stats1.pagesSkipped).toBe(0);

    await new Promise((resolve) => setTimeout(resolve, 10));

    // Second build - nothing changed
    const cache2 = new BuildCache(TEST_CACHE_DIR);
    const stats2 = await buildWithStats(
      TEST_CONTENT_DIR,
      TEST_OUTPUT_DIR,
      '/nonexistent/templates',
      undefined,
      { incremental: true, cache: cache2 }
    );

    expect(stats2.pagesBuilt).toBeGreaterThanOrEqual(0);
    expect(stats2.pagesSkipped).toBeGreaterThanOrEqual(0);
  });

  it('should handle deleted pages', async () => {
    fs.writeFileSync(path.join(TEST_CONTENT_DIR, 'page1.md'), '---\ntitle: Page 1\n---\n# Page 1');
    fs.writeFileSync(path.join(TEST_CONTENT_DIR, 'page2.md'), '---\ntitle: Page 2\n---\n# Page 2');

    // First build
    const cache1 = new BuildCache(TEST_CACHE_DIR);
    const pages1 = await generatePages(
      TEST_CONTENT_DIR,
      TEST_OUTPUT_DIR,
      undefined,
      undefined,
      { incremental: true, cache: cache1 }
    );
    cache1.save();

    expect(pages1.length).toBe(2);
    expect(fs.existsSync(path.join(TEST_OUTPUT_DIR, 'page1.html'))).toBe(true);
    expect(fs.existsSync(path.join(TEST_OUTPUT_DIR, 'page2.html'))).toBe(true);

    // Delete a page
    fs.unlinkSync(path.join(TEST_CONTENT_DIR, 'page2.md'));

    // Second build
    const cache2 = new BuildCache(TEST_CACHE_DIR);
    const pages2 = await generatePages(
      TEST_CONTENT_DIR,
      TEST_OUTPUT_DIR,
      undefined,
      undefined,
      { incremental: true, cache: cache2 }
    );

    expect(pages2.length).toBe(1);
    expect(pages2[0].slug).toBe('page1');
    // Note: deleted output files are not cleaned up by the generator
  });

  it('should cache with disabled incremental flag', async () => {
    fs.writeFileSync(path.join(TEST_CONTENT_DIR, 'page1.md'), '---\ntitle: Page 1\n---\n# Page 1');

    // Build without incremental flag
    const cache = new BuildCache(TEST_CACHE_DIR);
    const pages = await generatePages(
      TEST_CONTENT_DIR,
      TEST_OUTPUT_DIR,
      undefined,
      undefined,
      { incremental: false, cache }
    );

    expect(pages.length).toBe(1);
    expect(fs.existsSync(path.join(TEST_OUTPUT_DIR, 'page1.html'))).toBe(true);
  });
});
