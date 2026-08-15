import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import { SiteGenerator, BuildStats } from '../src/generator';
import { CacheManager } from '../src/cache-manager';

describe('Incremental Builds', () => {
  let tempDir: string;
  let contentDir: string;
  let outputDir: string;

  beforeEach(() => {
    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-incremental-test-'));
    contentDir = path.join(tempDir, 'content');
    outputDir = path.join(tempDir, 'dist');
    fs.mkdirSync(contentDir);
  });

  afterEach(() => {
    fs.rmSync(tempDir, { recursive: true, force: true });
  });

  it('should create cache manifest after build', async () => {
    fs.writeFileSync(
      path.join(contentDir, 'test.md'),
      '---\ntitle: Test\n---\n\nContent'
    );

    const generator = new SiteGenerator({ contentDir, outputDir, incremental: true });
    await generator.build();

    const cacheFile = path.join(outputDir, '.ssg-cache.json');
    expect(fs.existsSync(cacheFile)).toBe(true);

    const cacheContent = JSON.parse(fs.readFileSync(cacheFile, 'utf-8'));
    expect(cacheContent.entries['test.md']).toBeDefined();
    expect(cacheContent.entries['test.md'].fileHash).toBeDefined();
  });

  it('should skip unchanged files on incremental build', async () => {
    const markdownContent = '---\ntitle: Test\n---\n\nContent';
    fs.writeFileSync(path.join(contentDir, 'test.md'), markdownContent);

    const generator1 = new SiteGenerator({ contentDir, outputDir, incremental: true });
    await generator1.build();

    const stats1 = generator1.getBuildStats();
    expect(stats1.pagesBuilt).toBe(1);
    expect(stats1.pagesSkipped).toBe(0);

    const htmlPath = path.join(outputDir, 'test.html');
    const firstModTime = fs.statSync(htmlPath).mtimeMs;

    await new Promise(resolve => setTimeout(resolve, 100));

    const generator2 = new SiteGenerator({ contentDir, outputDir, incremental: true });
    await generator2.build();

    const stats2 = generator2.getBuildStats();
    expect(stats2.pagesBuilt).toBe(0);
    expect(stats2.pagesSkipped).toBe(1);

    const secondModTime = fs.statSync(htmlPath).mtimeMs;
    expect(secondModTime).toBe(firstModTime);
  });

  it('should rebuild file when content changes', async () => {
    const originalContent = '---\ntitle: Test\n---\n\nOriginal';
    fs.writeFileSync(path.join(contentDir, 'test.md'), originalContent);

    const generator1 = new SiteGenerator({ contentDir, outputDir, incremental: true });
    await generator1.build();

    const stats1 = generator1.getBuildStats();
    expect(stats1.pagesBuilt).toBe(1);

    await new Promise(resolve => setTimeout(resolve, 100));

    const updatedContent = '---\ntitle: Test\n---\n\nUpdated';
    fs.writeFileSync(path.join(contentDir, 'test.md'), updatedContent);

    const generator2 = new SiteGenerator({ contentDir, outputDir, incremental: true });
    await generator2.build();

    const stats2 = generator2.getBuildStats();
    expect(stats2.pagesBuilt).toBe(1);
    expect(stats2.pagesSkipped).toBe(0);

    const htmlContent = fs.readFileSync(path.join(outputDir, 'test.html'), 'utf-8');
    expect(htmlContent).toContain('Updated');
  });

  it('should rebuild file when template changes', async () => {
    const templatesDir = path.join(tempDir, 'templates');
    fs.mkdirSync(templatesDir);
    fs.mkdirSync(path.join(templatesDir, 'layouts'));

    const pageTemplate = '<div>{{content}}</div>';
    const layoutTemplate = '<html><body>{{{body}}}</body></html>';

    fs.writeFileSync(path.join(templatesDir, 'page.hbs'), pageTemplate);
    fs.writeFileSync(path.join(templatesDir, 'layouts', 'default.hbs'), layoutTemplate);

    fs.writeFileSync(
      path.join(contentDir, 'test.md'),
      '---\ntitle: Test\ntemplate: page\nlayout: default\n---\n\nContent'
    );

    const generator1 = new SiteGenerator({
      contentDir,
      outputDir,
      templatesDir,
      incremental: true,
    });
    await generator1.build();

    const stats1 = generator1.getBuildStats();
    expect(stats1.pagesBuilt).toBe(1);

    await new Promise(resolve => setTimeout(resolve, 100));

    const updatedPageTemplate = '<article>{{content}}</article>';
    fs.writeFileSync(path.join(templatesDir, 'page.hbs'), updatedPageTemplate);

    const generator2 = new SiteGenerator({
      contentDir,
      outputDir,
      templatesDir,
      incremental: true,
    });
    await generator2.build();

    const stats2 = generator2.getBuildStats();
    expect(stats2.pagesBuilt).toBe(1);
    expect(stats2.pagesSkipped).toBe(0);

    const htmlContent = fs.readFileSync(path.join(outputDir, 'test.html'), 'utf-8');
    expect(htmlContent).toContain('article');
  });

  it('should rebuild file when layout changes', async () => {
    const templatesDir = path.join(tempDir, 'templates');
    fs.mkdirSync(templatesDir);
    fs.mkdirSync(path.join(templatesDir, 'layouts'));

    const pageTemplate = '<div>{{content}}</div>';
    const layoutTemplate = '<html><body>{{{body}}}</body></html>';

    fs.writeFileSync(path.join(templatesDir, 'page.hbs'), pageTemplate);
    fs.writeFileSync(path.join(templatesDir, 'layouts', 'default.hbs'), layoutTemplate);

    fs.writeFileSync(
      path.join(contentDir, 'test.md'),
      '---\ntitle: Test\ntemplate: page\nlayout: default\n---\n\nContent'
    );

    const generator1 = new SiteGenerator({
      contentDir,
      outputDir,
      templatesDir,
      incremental: true,
    });
    await generator1.build();

    const stats1 = generator1.getBuildStats();
    expect(stats1.pagesBuilt).toBe(1);

    await new Promise(resolve => setTimeout(resolve, 100));

    const updatedLayoutTemplate = '<html><body class="updated">{{{body}}}</body></html>';
    fs.writeFileSync(path.join(templatesDir, 'layouts', 'default.hbs'), updatedLayoutTemplate);

    const generator2 = new SiteGenerator({
      contentDir,
      outputDir,
      templatesDir,
      incremental: true,
    });
    await generator2.build();

    const stats2 = generator2.getBuildStats();
    expect(stats2.pagesBuilt).toBe(1);
    expect(stats2.pagesSkipped).toBe(0);

    const htmlContent = fs.readFileSync(path.join(outputDir, 'test.html'), 'utf-8');
    expect(htmlContent).toContain('class="updated"');
  });

  it('should clean cache when --clean flag is used', async () => {
    fs.writeFileSync(
      path.join(contentDir, 'test.md'),
      '---\ntitle: Test\n---\n\nContent'
    );

    const generator1 = new SiteGenerator({ contentDir, outputDir, incremental: true });
    await generator1.build();

    const cacheFile = path.join(outputDir, '.ssg-cache.json');
    const cacheContent1 = JSON.parse(fs.readFileSync(cacheFile, 'utf-8'));
    expect(Object.keys(cacheContent1.entries).length).toBeGreaterThan(0);

    const generator2 = new SiteGenerator({ contentDir, outputDir, incremental: true, clean: true });
    await generator2.build();

    const cacheContent2 = JSON.parse(fs.readFileSync(cacheFile, 'utf-8'));
    expect(Object.keys(cacheContent2.entries).length).toBeGreaterThan(0);

    const stats = generator2.getBuildStats();
    expect(stats.pagesBuilt).toBe(1);
    expect(stats.pagesSkipped).toBe(0);
  });

  it('should handle multiple files with mixed changes', async () => {
    const file1 = '---\ntitle: File 1\n---\n\nContent 1';
    const file2 = '---\ntitle: File 2\n---\n\nContent 2';
    const file3 = '---\ntitle: File 3\n---\n\nContent 3';

    fs.writeFileSync(path.join(contentDir, 'file1.md'), file1);
    fs.writeFileSync(path.join(contentDir, 'file2.md'), file2);
    fs.writeFileSync(path.join(contentDir, 'file3.md'), file3);

    const generator1 = new SiteGenerator({ contentDir, outputDir, incremental: true });
    await generator1.build();

    const stats1 = generator1.getBuildStats();
    expect(stats1.pagesBuilt).toBe(3);

    await new Promise(resolve => setTimeout(resolve, 100));

    fs.writeFileSync(path.join(contentDir, 'file2.md'), '---\ntitle: File 2\n---\n\nUpdated');

    const generator2 = new SiteGenerator({ contentDir, outputDir, incremental: true });
    await generator2.build();

    const stats2 = generator2.getBuildStats();
    expect(stats2.pagesBuilt).toBe(1);
    expect(stats2.pagesSkipped).toBe(2);

    const file2Html = fs.readFileSync(path.join(outputDir, 'file2.html'), 'utf-8');
    expect(file2Html).toContain('Updated');
  });

  it('should perform full build when incremental is false', async () => {
    fs.writeFileSync(
      path.join(contentDir, 'test.md'),
      '---\ntitle: Test\n---\n\nContent'
    );

    const generator1 = new SiteGenerator({ contentDir, outputDir, incremental: false });
    await generator1.build();

    const stats1 = generator1.getBuildStats();
    expect(stats1.pagesBuilt).toBe(1);

    const generator2 = new SiteGenerator({ contentDir, outputDir, incremental: false });
    await generator2.build();

    const stats2 = generator2.getBuildStats();
    expect(stats2.pagesBuilt).toBe(1);
    expect(stats2.pagesSkipped).toBe(0);
  });

  it('should report build stats correctly', async () => {
    fs.writeFileSync(
      path.join(contentDir, 'test.md'),
      '---\ntitle: Test\n---\n\nContent'
    );

    const generator = new SiteGenerator({ contentDir, outputDir, incremental: true });
    await generator.build();

    const stats = generator.getBuildStats();
    expect(stats).toHaveProperty('pagesBuilt');
    expect(stats).toHaveProperty('pagesSkipped');
    expect(stats).toHaveProperty('totalTime');
    expect(stats.totalTime).toBeGreaterThanOrEqual(0);
  });

  it('should access cache manager from generator', async () => {
    fs.writeFileSync(
      path.join(contentDir, 'test.md'),
      '---\ntitle: Test\n---\n\nContent'
    );

    const generator = new SiteGenerator({ contentDir, outputDir, incremental: true });
    const cacheManager = generator.getCacheManager();

    expect(cacheManager).toBeInstanceOf(CacheManager);
  });

  it('should update cache after rebuild', async () => {
    fs.writeFileSync(
      path.join(contentDir, 'test.md'),
      '---\ntitle: Test\n---\n\nOriginal'
    );

    const generator1 = new SiteGenerator({ contentDir, outputDir, incremental: true });
    await generator1.build();

    const cacheManager1 = generator1.getCacheManager();
    const entry1 = cacheManager1.getEntry('test.md');
    expect(entry1).toBeDefined();
    expect(entry1?.html).toBeDefined();

    fs.writeFileSync(
      path.join(contentDir, 'test.md'),
      '---\ntitle: Test\n---\n\nUpdated'
    );

    const generator2 = new SiteGenerator({ contentDir, outputDir, incremental: true });
    await generator2.build();

    const cacheManager2 = generator2.getCacheManager();
    const entry2 = cacheManager2.getEntry('test.md');
    expect(entry2).toBeDefined();
    expect(entry2?.fileHash).not.toBe(entry1?.fileHash);
  });

  it('should preserve index generation with incremental builds', async () => {
    fs.writeFileSync(path.join(contentDir, 'file1.md'), '---\ntitle: File 1\n---\n\nContent 1');
    fs.writeFileSync(path.join(contentDir, 'file2.md'), '---\ntitle: File 2\n---\n\nContent 2');

    const generator1 = new SiteGenerator({ contentDir, outputDir, incremental: true });
    await generator1.build();

    let indexContent = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf-8');
    expect(indexContent).toContain('File 1');
    expect(indexContent).toContain('File 2');

    await new Promise(resolve => setTimeout(resolve, 100));

    fs.writeFileSync(path.join(contentDir, 'file1.md'), '---\ntitle: File 1 Updated\n---\n\nContent 1');

    const generator2 = new SiteGenerator({ contentDir, outputDir, incremental: true });
    await generator2.build();

    indexContent = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf-8');
    expect(indexContent).toContain('File 1 Updated');
    expect(indexContent).toContain('File 2');
  });

  it('should handle deleted files correctly', async () => {
    fs.writeFileSync(path.join(contentDir, 'file1.md'), '---\ntitle: File 1\n---\n\nContent 1');
    fs.writeFileSync(path.join(contentDir, 'file2.md'), '---\ntitle: File 2\n---\n\nContent 2');

    const generator1 = new SiteGenerator({ contentDir, outputDir, incremental: true });
    await generator1.build();

    expect(fs.existsSync(path.join(outputDir, 'file1.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'file2.html'))).toBe(true);

    await new Promise(resolve => setTimeout(resolve, 100));

    fs.unlinkSync(path.join(contentDir, 'file1.md'));

    const generator2 = new SiteGenerator({ contentDir, outputDir, incremental: true });
    await generator2.build();

    const stats2 = generator2.getBuildStats();
    expect(stats2.pagesBuilt).toBe(0);
    expect(stats2.pagesSkipped).toBe(1);

    expect(fs.existsSync(path.join(outputDir, 'file2.html'))).toBe(true);
  });

  it('should work with no markdown files', async () => {
    const generator = new SiteGenerator({ contentDir, outputDir, incremental: true });
    await generator.build();

    const stats = generator.getBuildStats();
    expect(stats.pagesBuilt).toBe(0);
    expect(stats.pagesSkipped).toBe(0);

    const indexPath = path.join(outputDir, 'index.html');
    expect(fs.existsSync(indexPath)).toBe(true);

    const indexContent = fs.readFileSync(indexPath, 'utf-8');
    expect(indexContent).toContain('No pages found');
  });
});

describe('CacheManager', () => {
  let tempDir: string;
  let outputDir: string;

  beforeEach(() => {
    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-cache-test-'));
    outputDir = path.join(tempDir, 'dist');
    fs.mkdirSync(outputDir);
  });

  afterEach(() => {
    fs.rmSync(tempDir, { recursive: true, force: true });
  });

  it('should create new cache manifest', () => {
    const cache = new CacheManager(outputDir);
    cache.saveManifest();

    const cacheFile = path.join(outputDir, '.ssg-cache.json');
    expect(fs.existsSync(cacheFile)).toBe(true);
  });

  it('should store and retrieve cache entries', () => {
    const cache = new CacheManager(outputDir);

    cache.updateEntry('test.md', 'content', '<html>test</html>');
    cache.saveManifest();

    const cache2 = new CacheManager(outputDir);
    const entry = cache2.getEntry('test.md');

    expect(entry).toBeDefined();
    expect(entry?.filename).toBe('test.md');
  });

  it('should detect file changes correctly', () => {
    const cache = new CacheManager(outputDir);

    cache.updateEntry('test.md', 'original content', '<html>test</html>');

    expect(cache.isFileChanged('test.md', 'original content')).toBe(false);
    expect(cache.isFileChanged('test.md', 'changed content')).toBe(true);
  });

  it('should clear all entries', () => {
    const cache = new CacheManager(outputDir);

    cache.updateEntry('test1.md', 'content1', '<html>1</html>');
    cache.updateEntry('test2.md', 'content2', '<html>2</html>');

    cache.clear();
    cache.saveManifest();

    const cache2 = new CacheManager(outputDir);
    expect(cache2.getEntry('test1.md')).toBeUndefined();
    expect(cache2.getEntry('test2.md')).toBeUndefined();
  });

  it('should get all cache entries', () => {
    const cache = new CacheManager(outputDir);

    cache.updateEntry('test1.md', 'content1', '<html>1</html>');
    cache.updateEntry('test2.md', 'content2', '<html>2</html>');

    const entries = cache.getEntries();
    expect(entries.length).toBe(2);
  });

  it('should get all filenames from cache', () => {
    const cache = new CacheManager(outputDir);

    cache.updateEntry('test1.md', 'content1', '<html>1</html>');
    cache.updateEntry('test2.md', 'content2', '<html>2</html>');

    const filenames = cache.getAllFilenames();
    expect(filenames).toContain('test1.md');
    expect(filenames).toContain('test2.md');
  });
});
