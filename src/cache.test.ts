import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { hashContent, hashFile, hashTemplatesDir, PageCache } from './cache';
import { Page } from './page';

function makeTmpDir(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

function makePage(overrides: Partial<Page> = {}): Page {
  return {
    slug: 'hello',
    title: 'Hello',
    date: null,
    tags: [],
    html: '<p>Hi</p>',
    sourcePath: '/tmp/hello.md',
    outputPath: 'hello.html',
    template: 'page',
    layout: 'default',
    ...overrides,
  };
}

describe('hashContent / hashFile', () => {
  it('produces identical hashes for identical content and different hashes for different content', () => {
    expect(hashContent('same')).toBe(hashContent('same'));
    expect(hashContent('same')).not.toBe(hashContent('different'));
  });

  it('hashes a file by its current contents', () => {
    const dir = makeTmpDir('ssg-hashfile-');
    try {
      const filePath = path.join(dir, 'a.txt');
      fs.writeFileSync(filePath, 'v1');
      const hashV1 = hashFile(filePath);
      expect(hashV1).toBe(hashContent('v1'));

      fs.writeFileSync(filePath, 'v2');
      expect(hashFile(filePath)).not.toBe(hashV1);
    } finally {
      fs.rmSync(dir, { recursive: true, force: true });
    }
  });
});

describe('hashTemplatesDir', () => {
  let templatesDir: string;

  beforeEach(() => {
    templatesDir = makeTmpDir('ssg-templates-hash-');
  });

  afterEach(() => {
    fs.rmSync(templatesDir, { recursive: true, force: true });
  });

  it('returns a stable hash regardless of filesystem iteration order', () => {
    fs.mkdirSync(path.join(templatesDir, 'layouts'));
    fs.writeFileSync(path.join(templatesDir, 'page.hbs'), 'PAGE');
    fs.writeFileSync(path.join(templatesDir, 'layouts', 'default.hbs'), 'LAYOUT');

    const first = hashTemplatesDir(templatesDir);
    const second = hashTemplatesDir(templatesDir);
    expect(first).toBe(second);
  });

  it('changes when a template file is edited', () => {
    fs.writeFileSync(path.join(templatesDir, 'page.hbs'), 'PAGE V1');
    const before = hashTemplatesDir(templatesDir);

    fs.writeFileSync(path.join(templatesDir, 'page.hbs'), 'PAGE V2');
    const after = hashTemplatesDir(templatesDir);

    expect(after).not.toBe(before);
  });

  it('changes when a template file is added', () => {
    fs.writeFileSync(path.join(templatesDir, 'page.hbs'), 'PAGE');
    const before = hashTemplatesDir(templatesDir);

    fs.writeFileSync(path.join(templatesDir, 'post.hbs'), 'POST');
    const after = hashTemplatesDir(templatesDir);

    expect(after).not.toBe(before);
  });

  it('ignores non-.hbs files', () => {
    fs.writeFileSync(path.join(templatesDir, 'page.hbs'), 'PAGE');
    const before = hashTemplatesDir(templatesDir);

    fs.writeFileSync(path.join(templatesDir, 'README.md'), 'not a template');
    const after = hashTemplatesDir(templatesDir);

    expect(after).toBe(before);
  });

  it('returns a hash for a missing templates directory instead of throwing', () => {
    expect(() => hashTemplatesDir(path.join(templatesDir, 'does-not-exist'))).not.toThrow();
  });
});

describe('PageCache', () => {
  let templatesDir: string;
  let cachePath: string;

  beforeEach(() => {
    templatesDir = makeTmpDir('ssg-cache-templates-');
    fs.writeFileSync(path.join(templatesDir, 'page.hbs'), 'PAGE');
    cachePath = path.join(makeTmpDir('ssg-cache-dir-'), '.ssg-cache.json');
  });

  afterEach(() => {
    fs.rmSync(templatesDir, { recursive: true, force: true });
    fs.rmSync(path.dirname(cachePath), { recursive: true, force: true });
  });

  it('starts empty when no manifest file exists yet', () => {
    const cache = new PageCache(cachePath, templatesDir, false);
    expect(cache.get('/some/source.md')).toBeUndefined();
  });

  it('round-trips an entry through set/get without saving', () => {
    const cache = new PageCache(cachePath, templatesDir, false);
    const entry = { sourceHash: 'abc', outputPath: 'hello.html', page: makePage(), buildTimeMs: 12 };
    cache.set('/some/source.md', entry);
    expect(cache.get('/some/source.md')).toEqual(entry);
  });

  it('persists entries to disk and reloads them in a fresh instance', () => {
    const cache = new PageCache(cachePath, templatesDir, false);
    const entry = { sourceHash: 'abc', outputPath: 'hello.html', page: makePage(), buildTimeMs: 12 };
    cache.set('/some/source.md', entry);
    cache.save();

    expect(fs.existsSync(cachePath)).toBe(true);

    const reloaded = new PageCache(cachePath, templatesDir, false);
    expect(reloaded.get('/some/source.md')).toEqual(entry);
  });

  it('discards all entries when the templates directory has changed since the manifest was written', () => {
    const cache = new PageCache(cachePath, templatesDir, false);
    cache.set('/some/source.md', { sourceHash: 'abc', outputPath: 'hello.html', page: makePage(), buildTimeMs: 12 });
    cache.save();

    fs.writeFileSync(path.join(templatesDir, 'page.hbs'), 'PAGE CHANGED');

    const reloaded = new PageCache(cachePath, templatesDir, false);
    expect(reloaded.get('/some/source.md')).toBeUndefined();
  });

  it('discards all entries when clean=true is passed, even if the manifest is valid', () => {
    const cache = new PageCache(cachePath, templatesDir, false);
    cache.set('/some/source.md', { sourceHash: 'abc', outputPath: 'hello.html', page: makePage(), buildTimeMs: 12 });
    cache.save();

    const cleaned = new PageCache(cachePath, templatesDir, true);
    expect(cleaned.get('/some/source.md')).toBeUndefined();
  });

  it('prunes entries whose source file is no longer part of the live set', () => {
    const cache = new PageCache(cachePath, templatesDir, false);
    cache.set('/live.md', { sourceHash: 'a', outputPath: 'live.html', page: makePage(), buildTimeMs: 1 });
    cache.set('/deleted.md', { sourceHash: 'b', outputPath: 'deleted.html', page: makePage(), buildTimeMs: 1 });

    cache.prune(new Set(['/live.md']));

    expect(cache.get('/live.md')).toBeDefined();
    expect(cache.get('/deleted.md')).toBeUndefined();
  });

  it('treats a corrupt manifest file as empty instead of throwing', () => {
    fs.mkdirSync(path.dirname(cachePath), { recursive: true });
    fs.writeFileSync(cachePath, 'not json');

    expect(() => new PageCache(cachePath, templatesDir, false)).not.toThrow();
    const cache = new PageCache(cachePath, templatesDir, false);
    expect(cache.get('/some/source.md')).toBeUndefined();
  });
});
