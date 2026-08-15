import fs from 'fs';
import path from 'path';
import os from 'os';
import { CacheManager } from './cache';

describe('CacheManager', () => {
  let tempDir: string;
  let outputDir: string;

  beforeEach(() => {
    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-cache-test-'));
    outputDir = tempDir;
  });

  afterEach(() => {
    fs.rmSync(tempDir, { recursive: true, force: true });
  });

  it('creates cache manager', () => {
    const manager = new CacheManager(outputDir);
    expect(manager).toBeDefined();
  });

  it('initializes with empty cache', () => {
    const manager = new CacheManager(outputDir);
    expect(manager['cacheData'].entries).toEqual({});
  });

  it('detects changed file when no cache exists', () => {
    const manager = new CacheManager(outputDir);
    const hasChanged = manager.hasChanged('test.md', 'content');
    expect(hasChanged).toBe(true);
  });

  it('detects unchanged file', () => {
    const manager = new CacheManager(outputDir);
    manager.updateEntry('test.md', 'content');
    manager.save();

    const manager2 = new CacheManager(outputDir);
    const hasChanged = manager2.hasChanged('test.md', 'content');
    expect(hasChanged).toBe(false);
  });

  it('detects changed content', () => {
    const manager = new CacheManager(outputDir);
    manager.updateEntry('test.md', 'content1');
    manager.save();

    const manager2 = new CacheManager(outputDir);
    const hasChanged = manager2.hasChanged('test.md', 'content2');
    expect(hasChanged).toBe(true);
  });

  it('saves cache to file', () => {
    const manager = new CacheManager(outputDir);
    manager.updateEntry('test.md', 'content');
    manager.save();

    const cachePath = path.join(outputDir, '.ssg-cache.json');
    expect(fs.existsSync(cachePath)).toBe(true);

    const data = JSON.parse(fs.readFileSync(cachePath, 'utf-8'));
    expect(data.entries['test.md']).toBeDefined();
    expect(data.entries['test.md'].hash).toBeDefined();
  });

  it('loads cache from file', () => {
    const manager = new CacheManager(outputDir);
    manager.updateEntry('test.md', 'content');
    manager.save();

    const manager2 = new CacheManager(outputDir);
    const hasChanged = manager2.hasChanged('test.md', 'content');
    expect(hasChanged).toBe(false);
  });

  it('tracks template changes', () => {
    const templatesDir = path.join(tempDir, 'templates');
    fs.mkdirSync(templatesDir, { recursive: true });
    const templatePath = path.join(templatesDir, 'default.hbs');
    fs.writeFileSync(templatePath, 'template1');

    const manager = new CacheManager(outputDir);
    manager.updateEntry('page.html', 'content', templatePath);
    manager.save();

    const manager2 = new CacheManager(outputDir);
    const hasChanged = manager2.hasChanged('page.html', 'content', templatePath);
    expect(hasChanged).toBe(false);

    // Modify template
    fs.writeFileSync(templatePath, 'template2');

    const hasChangedAfter = manager2.hasChanged('page.html', 'content', templatePath);
    expect(hasChangedAfter).toBe(true);
  });

  it('clears cache', () => {
    const manager = new CacheManager(outputDir);
    manager.updateEntry('test.md', 'content');
    manager.clear();

    expect(manager['cacheData'].entries).toEqual({});
  });

  it('computes build stats', () => {
    const manager = new CacheManager(outputDir);
    const stats = manager.getStats(5, 3);

    expect(stats.pagesBuilt).toBe(5);
    expect(stats.pagesSkipped).toBe(3);
    expect(stats.timeSaved).toBeGreaterThanOrEqual(0);
  });

  it('handles multiple file entries', () => {
    const manager = new CacheManager(outputDir);
    manager.updateEntry('page1.md', 'content1');
    manager.updateEntry('page2.md', 'content2');
    manager.updateEntry('page3.md', 'content3');
    manager.save();

    const manager2 = new CacheManager(outputDir);
    expect(manager2.hasChanged('page1.md', 'content1')).toBe(false);
    expect(manager2.hasChanged('page2.md', 'content2')).toBe(false);
    expect(manager2.hasChanged('page3.md', 'content3')).toBe(false);
    expect(manager2.hasChanged('page4.md', 'content4')).toBe(true);
  });

  it('handles corrupted cache file', () => {
    const cachePath = path.join(outputDir, '.ssg-cache.json');
    fs.writeFileSync(cachePath, 'invalid json {');

    const manager = new CacheManager(outputDir);
    expect(manager['cacheData'].entries).toEqual({});
  });

  it('detects content hash differences', () => {
    const manager = new CacheManager(outputDir);
    manager.updateEntry('test.md', 'content');
    manager.save();

    const manager2 = new CacheManager(outputDir);

    const hasChangedMinor = manager2.hasChanged('test.md', 'content ');
    expect(hasChangedMinor).toBe(true);

    const hasChangedCasing = manager2.hasChanged('test.md', 'Content');
    expect(hasChangedCasing).toBe(true);
  });

  it('tracks separate cache entries for different files', () => {
    const manager = new CacheManager(outputDir);
    manager.updateEntry('page1.html', 'html1');
    manager.updateEntry('page2.html', 'html2');
    manager.save();

    const manager2 = new CacheManager(outputDir);

    const page1Changed = manager2.hasChanged('page1.html', 'html1');
    const page2Changed = manager2.hasChanged('page2.html', 'html2');

    expect(page1Changed).toBe(false);
    expect(page2Changed).toBe(false);

    const page1UpdateChanged = manager2.hasChanged('page1.html', 'html_updated');
    expect(page1UpdateChanged).toBe(true);

    const page2Unchanged = manager2.hasChanged('page2.html', 'html2');
    expect(page2Unchanged).toBe(false);
  });
});
