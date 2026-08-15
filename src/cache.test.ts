import { promises as fs } from 'fs';
import path from 'path';
import { CacheManager, BuildStats } from './cache';

const testDir = path.join(__dirname, '..', '__test_cache__');

async function cleanup(): Promise<void> {
  try {
    await fs.rm(testDir, { recursive: true, force: true });
  } catch (e) {
    // ignored
  }
}

describe('CacheManager', () => {
  beforeEach(async () => {
    await cleanup();
  });

  afterEach(async () => {
    await cleanup();
  });

  describe('cache file management', () => {
    it('should initialize with empty manifest', () => {
      const manager = new CacheManager(testDir);
      expect(manager).toBeDefined();
    });

    it('should load empty cache when file does not exist', async () => {
      const manager = new CacheManager(testDir);
      await manager.load();
      // Should not throw
    });

    it('should save cache to file', async () => {
      const manager = new CacheManager(testDir);
      manager.updateEntry('test', 'content', '<html>test</html>');
      await manager.save();

      const cacheFile = path.join(testDir, '.ssg-cache.json');
      const exists = await fs.stat(cacheFile).then(() => true).catch(() => false);
      expect(exists).toBe(true);

      const content = await fs.readFile(cacheFile, 'utf-8');
      const data = JSON.parse(content);
      expect(data.entries.test).toBeDefined();
    });

    it('should load existing cache', async () => {
      const cacheDir = path.join(testDir, 'output');
      await fs.mkdir(cacheDir, { recursive: true });

      const cacheData = {
        version: '1',
        entries: {
          'test': {
            sourceHash: 'abc123',
            renderedHtml: '<html>cached</html>',
            timestamp: Date.now()
          }
        }
      };

      await fs.writeFile(
        path.join(cacheDir, '.ssg-cache.json'),
        JSON.stringify(cacheData),
        'utf-8'
      );

      const manager = new CacheManager(cacheDir);
      await manager.load();

      const cached = manager.getCachedHtml('test');
      expect(cached).toBe('<html>cached</html>');
    });
  });

  describe('change detection', () => {
    it('should detect changed source content', async () => {
      const manager = new CacheManager(testDir);
      await manager.load();

      const sourceContent = '# Hello World';
      const renderedHtml = '<h1>Hello World</h1>';

      manager.updateEntry('test', sourceContent, renderedHtml);

      const isChanged = await manager.isPageChanged('test', sourceContent);
      expect(isChanged).toBe(false);

      const newContent = '# Hello World Updated';
      const isChangedAfterUpdate = await manager.isPageChanged('test', newContent);
      expect(isChangedAfterUpdate).toBe(true);
    });

    it('should detect new pages', async () => {
      const manager = new CacheManager(testDir);
      await manager.load();

      const sourceContent = '# New Post';
      const isChanged = await manager.isPageChanged('newpage', sourceContent);
      expect(isChanged).toBe(true);
    });

    it('should detect template changes', async () => {
      const manager = new CacheManager(testDir);
      await manager.load();

      const sourceContent = '# Post';
      const templateContent = '<div>{{body}}</div>';
      const renderedHtml = '<div><h1>Post</h1></div>';

      manager.updateEntry('test', sourceContent, renderedHtml, templateContent);

      const isChanged = await manager.isPageChanged('test', sourceContent, templateContent);
      expect(isChanged).toBe(false);

      const newTemplate = '<div class="post">{{body}}</div>';
      const isChangedAfterTemplate = await manager.isPageChanged('test', sourceContent, newTemplate);
      expect(isChangedAfterTemplate).toBe(true);
    });

    it('should detect layout changes', async () => {
      const manager = new CacheManager(testDir);
      await manager.load();

      const sourceContent = '# Post';
      const layoutContent = '<html>{{body}}</html>';
      const renderedHtml = '<html><h1>Post</h1></html>';

      manager.updateEntry('test', sourceContent, renderedHtml, undefined, layoutContent);

      const isChanged = await manager.isPageChanged('test', sourceContent, undefined, layoutContent);
      expect(isChanged).toBe(false);

      const newLayout = '<html><body>{{body}}</body></html>';
      const isChangedAfterLayout = await manager.isPageChanged('test', sourceContent, undefined, newLayout);
      expect(isChangedAfterLayout).toBe(true);
    });

    it('should detect when template or layout is added', async () => {
      const manager = new CacheManager(testDir);
      await manager.load();

      const sourceContent = '# Post';
      const renderedHtml = '<h1>Post</h1>';

      manager.updateEntry('test', sourceContent, renderedHtml);

      const isChanged = await manager.isPageChanged('test', sourceContent, '<div>{{body}}</div>');
      expect(isChanged).toBe(true);
    });
  });

  describe('cache retrieval', () => {
    it('should retrieve cached HTML', async () => {
      const manager = new CacheManager(testDir);
      const renderedHtml = '<html><h1>Test</h1></html>';

      manager.updateEntry('test', '# Test', renderedHtml);

      const cached = manager.getCachedHtml('test');
      expect(cached).toBe(renderedHtml);
    });

    it('should return undefined for uncached pages', async () => {
      const manager = new CacheManager(testDir);

      const cached = manager.getCachedHtml('nonexistent');
      expect(cached).toBeUndefined();
    });

    it('should handle multiple cached pages', async () => {
      const manager = new CacheManager(testDir);

      manager.updateEntry('post1', '# Post 1', '<h1>Post 1</h1>');
      manager.updateEntry('post2', '# Post 2', '<h1>Post 2</h1>');
      manager.updateEntry('post3', '# Post 3', '<h1>Post 3</h1>');

      expect(manager.getCachedHtml('post1')).toBe('<h1>Post 1</h1>');
      expect(manager.getCachedHtml('post2')).toBe('<h1>Post 2</h1>');
      expect(manager.getCachedHtml('post3')).toBe('<h1>Post 3</h1>');
    });
  });

  describe('build statistics', () => {
    it('should calculate build stats correctly', () => {
      const manager = new CacheManager(testDir);

      manager.recordPageBuildTime('post1', 100);
      manager.recordPageBuildTime('post2', 150);
      manager.recordPageBuildTime('post3', 120);

      const skipped = new Set(['post1', 'post2']);
      const stats = manager.getStats(3, skipped);

      expect(stats.pagesBuilt).toBe(1);
      expect(stats.pagesSkipped).toBe(2);
      expect(stats.totalPages).toBe(3);
      expect(stats.timeSaved).toBeGreaterThan(0);
    });

    it('should report zero time saved when all pages built', () => {
      const manager = new CacheManager(testDir);

      manager.recordPageBuildTime('post1', 100);

      const skipped = new Set<string>();
      const stats = manager.getStats(1, skipped);

      expect(stats.pagesBuilt).toBe(1);
      expect(stats.pagesSkipped).toBe(0);
      expect(stats.timeSaved).toBe(0);
    });

    it('should estimate time saved for skipped pages without recorded time', () => {
      const manager = new CacheManager(testDir);

      const skipped = new Set(['post1', 'post2']);
      const stats = manager.getStats(3, skipped);

      expect(stats.pagesBuilt).toBe(1);
      expect(stats.pagesSkipped).toBe(2);
      expect(stats.timeSaved).toBeGreaterThan(0);
    });
  });

  describe('cache clearing', () => {
    it('should clear all cache entries', () => {
      const manager = new CacheManager(testDir);

      manager.updateEntry('post1', '# Post 1', '<h1>Post 1</h1>');
      manager.updateEntry('post2', '# Post 2', '<h1>Post 2</h1>');

      manager.clear();

      expect(manager.getCachedHtml('post1')).toBeUndefined();
      expect(manager.getCachedHtml('post2')).toBeUndefined();
    });
  });

  describe('hash consistency', () => {
    it('should produce consistent hashes for same content', async () => {
      const manager = new CacheManager(testDir);

      const content = '# Hello World\n\nThis is a test.';
      const sourceContent = content;
      const templateContent = '<div>{{body}}</div>';

      manager.updateEntry('test1', sourceContent, '<p>Test</p>', templateContent);
      await manager.save();

      const manager2 = new CacheManager(testDir);
      await manager2.load();

      const isChanged = await manager2.isPageChanged('test1', sourceContent, templateContent);
      expect(isChanged).toBe(false);
    });

    it('should detect minimal content changes', async () => {
      const manager = new CacheManager(testDir);

      const originalContent = '# Hello World';
      manager.updateEntry('test', originalContent, '<h1>Hello World</h1>');

      const modifiedContent = '# Hello World ';
      const isChanged = await manager.isPageChanged('test', modifiedContent);
      expect(isChanged).toBe(true);
    });
  });
});
