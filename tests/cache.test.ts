import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import {
  CACHE_VERSION,
  deleteCacheManifest,
  hashDirectory,
  hashFile,
  hashString,
  loadCacheManifest,
  saveCacheManifest,
  type CacheManifest,
} from '../src/cache';

function makeTempDir(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

function writeFile(filePath: string, content: string): void {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, content, 'utf8');
}

describe('cache', () => {
  describe('hashString / hashFile', () => {
    it('produces the same hash for identical content', () => {
      expect(hashString('hello')).toBe(hashString('hello'));
    });

    it('produces different hashes for different content', () => {
      expect(hashString('hello')).not.toBe(hashString('world'));
    });

    it('hashes a file by its contents', () => {
      const dir = makeTempDir('ssg-cache-hashfile-');
      try {
        const filePath = path.join(dir, 'a.txt');
        writeFile(filePath, 'A body');
        expect(hashFile(filePath)).toBe(hashString('A body'));
      } finally {
        fs.rmSync(dir, { recursive: true, force: true });
      }
    });
  });

  describe('hashDirectory', () => {
    let dir: string;

    beforeEach(() => {
      dir = makeTempDir('ssg-cache-hashdir-');
    });

    afterEach(() => {
      fs.rmSync(dir, { recursive: true, force: true });
    });

    it('returns an empty string when the directory does not exist', () => {
      expect(hashDirectory(path.join(dir, 'nope'))).toBe('');
    });

    it('is stable across calls when nothing changes', () => {
      writeFile(path.join(dir, 'layouts', 'default.hbs'), '<html>{{{body}}}</html>');
      writeFile(path.join(dir, 'partials', 'nav.hbs'), '<nav></nav>');

      expect(hashDirectory(dir)).toBe(hashDirectory(dir));
    });

    it('changes when a file under the directory is edited', () => {
      writeFile(path.join(dir, 'layouts', 'default.hbs'), '<html>{{{body}}}</html>');
      const before = hashDirectory(dir);

      writeFile(path.join(dir, 'layouts', 'default.hbs'), '<html class="v2">{{{body}}}</html>');
      const after = hashDirectory(dir);

      expect(after).not.toBe(before);
    });

    it('changes when a file is added, independent of traversal order', () => {
      writeFile(path.join(dir, 'layouts', 'default.hbs'), '<html>{{{body}}}</html>');
      const before = hashDirectory(dir);

      writeFile(path.join(dir, 'partials', 'nav.hbs'), '<nav></nav>');
      const after = hashDirectory(dir);

      expect(after).not.toBe(before);
    });
  });

  describe('manifest persistence', () => {
    let cachePath: string;

    beforeEach(() => {
      cachePath = path.join(makeTempDir('ssg-cache-manifest-'), '.ssg-cache.json');
    });

    afterEach(() => {
      fs.rmSync(path.dirname(cachePath), { recursive: true, force: true });
    });

    it('returns undefined when the manifest file does not exist', () => {
      expect(loadCacheManifest(cachePath)).toBeUndefined();
    });

    it('round-trips a manifest through save and load', () => {
      const manifest: CacheManifest = {
        version: CACHE_VERSION,
        templatesHash: 'abc123',
        pluginsSignature: 'markdown|template',
        pages: {
          'a.md': {
            sourceHash: 'hash-a',
            buildTimeMs: 5,
            page: {
              slug: 'a',
              title: 'A',
              tags: [],
              html: '<p>A</p>',
              sourcePath: 'a.md',
              outputFile: 'a.html',
            },
          },
        },
      };

      saveCacheManifest(cachePath, manifest);
      expect(loadCacheManifest(cachePath)).toEqual(manifest);
    });

    it('returns undefined for a manifest written with an incompatible version', () => {
      fs.mkdirSync(path.dirname(cachePath), { recursive: true });
      fs.writeFileSync(cachePath, JSON.stringify({ version: CACHE_VERSION + 1, pages: {} }), 'utf8');
      expect(loadCacheManifest(cachePath)).toBeUndefined();
    });

    it('returns undefined for malformed JSON instead of throwing', () => {
      fs.mkdirSync(path.dirname(cachePath), { recursive: true });
      fs.writeFileSync(cachePath, '{ not valid json', 'utf8');
      expect(loadCacheManifest(cachePath)).toBeUndefined();
    });

    it('deleteCacheManifest removes an existing manifest and is a no-op otherwise', () => {
      saveCacheManifest(cachePath, {
        version: CACHE_VERSION,
        templatesHash: '',
        pluginsSignature: '',
        pages: {},
      });
      expect(fs.existsSync(cachePath)).toBe(true);

      deleteCacheManifest(cachePath);
      expect(fs.existsSync(cachePath)).toBe(false);

      expect(() => deleteCacheManifest(cachePath)).not.toThrow();
    });
  });
});
