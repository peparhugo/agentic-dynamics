import { promises as fs } from 'fs';
import path from 'path';
import { build } from './build';

const testDir = path.join(__dirname, '..', '__test_incremental__');
const contentDir = path.join(testDir, 'content');
const outputDir = path.join(testDir, 'dist');
const templateDir = path.join(testDir, 'templates');

async function cleanup(): Promise<void> {
  try {
    await fs.rm(testDir, { recursive: true, force: true });
  } catch (e) {
    // ignored
  }
}

async function setupTestContent(): Promise<void> {
  await fs.mkdir(contentDir, { recursive: true });
  await fs.mkdir(templateDir, { recursive: true });

  const post1 = `---
title: Post 1
date: 2024-01-15
---

# Post 1

Content for post 1.`;

  const post2 = `---
title: Post 2
date: 2024-01-16
---

# Post 2

Content for post 2.`;

  await fs.writeFile(path.join(contentDir, 'post1.md'), post1);
  await fs.writeFile(path.join(contentDir, 'post2.md'), post2);
}

describe('Incremental Build', () => {
  beforeEach(async () => {
    await cleanup();
  });

  afterEach(async () => {
    await cleanup();
  });

  describe('basic incremental build', () => {
    it('should perform full build when cache does not exist', async () => {
      await setupTestContent();

      const stats = await build(contentDir, outputDir, templateDir, false, { incremental: true });

      expect(stats).toBeDefined();
      expect(stats?.pagesBuilt).toBe(2);
      expect(stats?.pagesSkipped).toBe(0);
      expect(stats?.totalPages).toBe(2);

      const post1Exists = await fs.stat(path.join(outputDir, 'post1.html')).then(() => true).catch(() => false);
      const post2Exists = await fs.stat(path.join(outputDir, 'post2.html')).then(() => true).catch(() => false);
      const indexExists = await fs.stat(path.join(outputDir, 'index.html')).then(() => true).catch(() => false);

      expect(post1Exists).toBe(true);
      expect(post2Exists).toBe(true);
      expect(indexExists).toBe(true);

      const cacheExists = await fs.stat(path.join(outputDir, '.ssg-cache.json')).then(() => true).catch(() => false);
      expect(cacheExists).toBe(true);
    });

    it('should skip unchanged pages in subsequent builds', async () => {
      await setupTestContent();

      const firstStats = await build(contentDir, outputDir, templateDir, false, { incremental: true });
      expect(firstStats?.pagesBuilt).toBe(2);

      const secondStats = await build(contentDir, outputDir, templateDir, false, { incremental: true });
      expect(secondStats?.pagesBuilt).toBe(0);
      expect(secondStats?.pagesSkipped).toBe(2);
      expect(secondStats?.totalPages).toBe(2);
    });

    it('should rebuild only changed pages', async () => {
      await setupTestContent();

      await build(contentDir, outputDir, templateDir, false, { incremental: true });

      const post1UpdatedContent = `---
title: Post 1 Updated
date: 2024-01-15
---

# Post 1 Updated

Modified content for post 1.`;

      await fs.writeFile(path.join(contentDir, 'post1.md'), post1UpdatedContent);

      const secondStats = await build(contentDir, outputDir, templateDir, false, { incremental: true });
      expect(secondStats?.pagesBuilt).toBe(1);
      expect(secondStats?.pagesSkipped).toBe(1);
      expect(secondStats?.totalPages).toBe(2);

      const post1Content = await fs.readFile(path.join(outputDir, 'post1.html'), 'utf-8');
      expect(post1Content).toContain('Post 1 Updated');
    });
  });

  describe('cache clearing', () => {
    it('should rebuild all pages with --clean flag', async () => {
      await setupTestContent();

      await build(contentDir, outputDir, templateDir, false, { incremental: true });

      const stats = await build(contentDir, outputDir, templateDir, false, { incremental: true, clean: true });
      expect(stats?.pagesBuilt).toBe(2);
      expect(stats?.pagesSkipped).toBe(0);
      expect(stats?.totalPages).toBe(2);
    });
  });

  describe('new and deleted pages', () => {
    it('should detect new pages and build them', async () => {
      await setupTestContent();

      const firstStats = await build(contentDir, outputDir, templateDir, false, { incremental: true });
      expect(firstStats?.pagesBuilt).toBe(2);

      const post3Content = `---
title: Post 3
date: 2024-01-17
---

# Post 3

Content for post 3.`;

      await fs.writeFile(path.join(contentDir, 'post3.md'), post3Content);

      const secondStats = await build(contentDir, outputDir, templateDir, false, { incremental: true });
      expect(secondStats?.pagesBuilt).toBe(1);
      expect(secondStats?.pagesSkipped).toBe(2);
      expect(secondStats?.totalPages).toBe(3);

      const post3Exists = await fs.stat(path.join(outputDir, 'post3.html')).then(() => true).catch(() => false);
      expect(post3Exists).toBe(true);

      const indexContent = await fs.readFile(path.join(outputDir, 'index.html'), 'utf-8');
      expect(indexContent).toContain('Total: 3 pages');
    });

    it('should handle multiple consecutive incremental builds', async () => {
      await setupTestContent();

      const stats1 = await build(contentDir, outputDir, templateDir, false, { incremental: true });
      expect(stats1?.pagesBuilt).toBe(2);
      expect(stats1?.pagesSkipped).toBe(0);

      const stats2 = await build(contentDir, outputDir, templateDir, false, { incremental: true });
      expect(stats2?.pagesBuilt).toBe(0);
      expect(stats2?.pagesSkipped).toBe(2);

      const post1 = `---
title: Post 1 V2
date: 2024-01-15
---

# Post 1 V2

Content version 2.`;

      await fs.writeFile(path.join(contentDir, 'post1.md'), post1);

      const stats3 = await build(contentDir, outputDir, templateDir, false, { incremental: true });
      expect(stats3?.pagesBuilt).toBe(1);
      expect(stats3?.pagesSkipped).toBe(1);

      const stats4 = await build(contentDir, outputDir, templateDir, false, { incremental: true });
      expect(stats4?.pagesBuilt).toBe(0);
      expect(stats4?.pagesSkipped).toBe(2);
    });
  });

  describe('backward compatibility', () => {
    it('should work with non-incremental builds', async () => {
      await setupTestContent();

      const stats = await build(contentDir, outputDir, templateDir, false, { incremental: false });
      expect(stats).toBeUndefined();

      const post1Exists = await fs.stat(path.join(outputDir, 'post1.html')).then(() => true).catch(() => false);
      expect(post1Exists).toBe(true);
    });

    it('should skip incremental flag when not specified', async () => {
      await setupTestContent();

      await build(contentDir, outputDir, templateDir, false);

      const cacheExists = await fs.stat(path.join(outputDir, '.ssg-cache.json')).then(() => true).catch(() => false);
      expect(cacheExists).toBe(false);
    });
  });

  describe('cache file integrity', () => {
    it('should create valid cache manifest', async () => {
      await setupTestContent();

      await build(contentDir, outputDir, templateDir, false, { incremental: true });

      const cacheFile = path.join(outputDir, '.ssg-cache.json');
      const cacheContent = await fs.readFile(cacheFile, 'utf-8');
      const cache = JSON.parse(cacheContent);

      expect(cache.version).toBe('1');
      expect(cache.entries).toBeDefined();
      expect(cache.entries.post1).toBeDefined();
      expect(cache.entries.post2).toBeDefined();
      expect(cache.entries.post1.sourceHash).toBeDefined();
      expect(cache.entries.post1.timestamp).toBeDefined();
    });

    it('should preserve cache across multiple builds', async () => {
      await setupTestContent();

      const stats1 = await build(contentDir, outputDir, templateDir, false, { incremental: true });

      const cacheFile = path.join(outputDir, '.ssg-cache.json');
      const cacheAfterFirst = await fs.readFile(cacheFile, 'utf-8');

      const stats2 = await build(contentDir, outputDir, templateDir, false, { incremental: true });

      const cacheAfterSecond = await fs.readFile(cacheFile, 'utf-8');

      expect(cacheAfterFirst).toBe(cacheAfterSecond);
      expect(stats2?.pagesSkipped).toBe(2);
    });
  });

  describe('build statistics reporting', () => {
    it('should return correct statistics on full build', async () => {
      await setupTestContent();

      const stats = await build(contentDir, outputDir, templateDir, false, { incremental: true });

      expect(stats?.pagesBuilt).toBe(2);
      expect(stats?.pagesSkipped).toBe(0);
      expect(stats?.totalPages).toBe(2);
      expect(stats?.timeSaved).toBeGreaterThanOrEqual(0);
    });

    it('should return correct statistics on incremental build', async () => {
      await setupTestContent();

      await build(contentDir, outputDir, templateDir, false, { incremental: true });

      const stats = await build(contentDir, outputDir, templateDir, false, { incremental: true });

      expect(stats?.pagesBuilt).toBe(0);
      expect(stats?.pagesSkipped).toBe(2);
      expect(stats?.totalPages).toBe(2);
      expect(stats?.timeSaved).toBeGreaterThan(0);
    });
  });
});
