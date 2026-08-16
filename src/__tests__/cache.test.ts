import fs from 'fs';
import os from 'os';
import path from 'path';

import {
  CACHE_FILE_NAME,
  CACHE_VERSION,
  EMPTY_TEMPLATE_HASH,
  cacheFilePath,
  computeTemplateHash,
  hashContent,
  hashFile,
  loadCache,
  saveCache,
} from '../cache';
import type { CacheManifest } from '../cache';

function writeTree(root: string, files: Record<string, string>): void {
  for (const [rel, contents] of Object.entries(files)) {
    const full = path.join(root, rel);
    fs.mkdirSync(path.dirname(full), { recursive: true });
    fs.writeFileSync(full, contents);
  }
}

describe('hashContent', () => {
  it('is deterministic and sensitive to content', () => {
    expect(hashContent('hello')).toBe(hashContent('hello'));
    expect(hashContent('hello')).not.toBe(hashContent('world'));
    expect(hashContent('')).toBe(hashContent(''));
  });
});

describe('hashFile', () => {
  it('hashes a file based on its contents', () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-hash-'));
    const file = path.join(dir, 'a.md');
    fs.writeFileSync(file, '# hi');

    expect(hashFile(file)).toBe(hashContent('# hi'));
    fs.writeFileSync(file, '# bye');
    expect(hashFile(file)).toBe(hashContent('# bye'));
    fs.rmSync(dir, { recursive: true, force: true });
  });

  it('returns the empty-content hash for a missing file', () => {
    expect(hashFile(path.join(os.tmpdir(), 'nope-ssg.md'))).toBe(hashContent(''));
  });
});

describe('computeTemplateHash', () => {
  it('returns a stable hash when no templates directory exists', () => {
    const missing = path.join(os.tmpdir(), 'missing-templates-ssg');
    expect(computeTemplateHash(missing)).toBe(EMPTY_TEMPLATE_HASH);
    expect(computeTemplateHash(missing)).toBe(computeTemplateHash(missing));
  });

  it('changes when a template file is added, edited or removed', () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-tpl-hash-'));
    const before = computeTemplateHash(dir);
    expect(before).toBe(EMPTY_TEMPLATE_HASH);

    writeTree(dir, { 'default.hbs': '<article>{{title}}</article>' });
    const withTemplate = computeTemplateHash(dir);
    expect(withTemplate).not.toBe(before);

    writeTree(dir, { 'default.hbs': '<article>{{title}}!</article>' });
    expect(computeTemplateHash(dir)).not.toBe(withTemplate);

    writeTree(dir, {
      'layouts/default.hbs': '<html>{{{body}}}</html>',
      'partials/header.hbs': '<header>h</header>',
    });
    const withNested = computeTemplateHash(dir);
    expect(withNested).not.toBe(withTemplate);

    fs.rmSync(dir, { recursive: true, force: true });
    expect(computeTemplateHash(dir)).toBe(EMPTY_TEMPLATE_HASH);
  });
});

describe('cacheFilePath', () => {
  it('places the manifest inside the output directory', () => {
    expect(cacheFilePath('/tmp/site/dist')).toBe(
      path.join('/tmp/site/dist', CACHE_FILE_NAME),
    );
  });
});

describe('saveCache / loadCache', () => {
  let dir: string;
  let cachePath: string;

  beforeEach(() => {
    dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-cache-'));
    cachePath = path.join(dir, CACHE_FILE_NAME);
  });

  afterEach(() => {
    fs.rmSync(dir, { recursive: true, force: true });
  });

  it('round-trips a manifest through disk', () => {
    const manifest: CacheManifest = {
      version: CACHE_VERSION,
      entries: {
        'a.html': {
          sourceHash: hashContent('# a'),
          templateHash: EMPTY_TEMPLATE_HASH,
          page: {
            slug: 'a',
            sourcePath: path.join(dir, 'a.md'),
            outputName: 'a.html',
            title: 'A',
            tags: ['t'],
            html: '<p>a</p>',
            content: '# a',
            raw: '# a',
            data: { title: 'A', tags: ['t'] },
          },
          output: '<html>a</html>',
          buildMs: 12.5,
          builtAt: '2026-01-01T00:00:00.000Z',
        },
      },
    };

    saveCache(cachePath, manifest);
    expect(fs.existsSync(cachePath)).toBe(true);

    const loaded = loadCache(cachePath);
    expect(loaded).not.toBeNull();
    expect(loaded!.entries['a.html'].sourceHash).toBe(manifest.entries['a.html'].sourceHash);
    expect(loaded!.entries['a.html'].output).toBe('<html>a</html>');
    expect(loaded!.entries['a.html'].page!.data.title).toBe('A');
    expect(loaded!.entries['a.html'].buildMs).toBe(12.5);
  });

  it('returns null for a missing manifest', () => {
    expect(loadCache(path.join(dir, 'missing.json'))).toBeNull();
  });

  it('returns null for a corrupt manifest', () => {
    fs.writeFileSync(cachePath, '{ not json');
    expect(loadCache(cachePath)).toBeNull();
  });

  it('returns null for an unsupported manifest version', () => {
    fs.writeFileSync(cachePath, JSON.stringify({ version: CACHE_VERSION + 1, entries: {} }));
    expect(loadCache(cachePath)).toBeNull();
  });
});
