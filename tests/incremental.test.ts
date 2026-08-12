import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'fs';
import { join } from 'path';
import { buildSiteIncremental } from '../src/build';
import { run, parseArgs, BuildOptions } from '../src/cli';
import {
  CACHE_FILE_NAME,
  CACHE_VERSION,
  computeTemplateHash,
  hashContent,
  hashFile,
  IncrementalCache,
  toPosixPath,
} from '../src/cache';
import { createFixture, cleanupFixture, Fixture } from './helpers';

describe('hash helpers', () => {
  it('produces a stable content hash', () => {
    const first = hashContent('hello world');
    const second = hashContent('hello world');
    const other = hashContent('hello world!');
    expect(first).toBe(second);
    expect(first).not.toBe(other);
    expect(first).toMatch(/^[a-f0-9]{64}$/);
  });

  it('hashes a file on disk', () => {
    const fixture = createFixture({ 'a.md': 'abc' });
    try {
      expect(hashFile(join(fixture.contentDir, 'a.md'))).toBe(hashContent('abc'));
    } finally {
      cleanupFixture(fixture);
    }
  });

  it('changes the template hash when a template file changes', () => {
    const fixture = createFixture({ 'a.md': '# A' }, { 'default.hbs': 'OLD {{{content}}}' });
    try {
      const before = computeTemplateHash(fixture.templatesDir);
      writeFileSync(join(fixture.templatesDir, 'default.hbs'), 'NEW {{{content}}}');
      const after = computeTemplateHash(fixture.templatesDir);
      expect(after).not.toBe(before);

      const noTemplates = computeTemplateHash(join(fixture.root, 'missing-templates'));
      expect(noTemplates).toBe(computeTemplateHash(join(fixture.root, 'missing-templates')));
    } finally {
      cleanupFixture(fixture);
    }
  });

  it('normalizes relative paths to posix separators', () => {
    expect(toPosixPath('nested/inner.md')).toBe('nested/inner.md');
  });
});

describe('IncrementalCache', () => {
  let fixture: Fixture;

  beforeEach(() => {
    fixture = createFixture({ 'a.md': '# A' });
  });

  afterEach(() => {
    cleanupFixture(fixture);
  });

  it('starts empty when no manifest exists', () => {
    const cache = IncrementalCache.load(fixture.outputDir, false);
    expect(cache.templateHash).toBe('');
    expect(cache.pages).toEqual({});
  });

  it('ignores a stale manifest when clean is requested', () => {
    const first = IncrementalCache.load(fixture.outputDir, false);
    first.setTemplateHash('abc');
    first.set('a.md', {
      sourceHash: 'x',
      frontmatter: { title: 'A' },
      contentHtml: '<p>A</p>',
      html: '<p>A</p>',
      buildTimeMs: 5,
    });
    first.save();

    const clean = IncrementalCache.load(fixture.outputDir, true);
    expect(clean.pages).toEqual({});
  });

  it('round-trips page data through save and load', () => {
    const cache = IncrementalCache.load(fixture.outputDir, false);
    cache.setTemplateHash('tpl-hash');
    cache.set('a.md', {
      sourceHash: 'src-hash',
      frontmatter: { title: 'A', tags: ['x'] },
      contentHtml: '<p>A</p>',
      html: '<p>A</p>',
      buildTimeMs: 7,
    });
    cache.save();

    const loaded = IncrementalCache.load(fixture.outputDir, false);
    expect(loaded.templateHash).toBe('tpl-hash');
    const page = loaded.get('a.md');
    expect(page).toBeDefined();
    expect(page?.sourceHash).toBe('src-hash');
    expect(page?.frontmatter.title).toBe('A');
    expect(page?.buildTimeMs).toBe(7);
    loaded.delete('a.md');
    expect(loaded.get('a.md')).toBeUndefined();
  });

  it('writes a valid manifest version', () => {
    const cache = IncrementalCache.load(fixture.outputDir, false);
    cache.save();
    const manifest = JSON.parse(readFileSync(join(fixture.outputDir, CACHE_FILE_NAME), 'utf8'));
    expect(manifest.version).toBe(CACHE_VERSION);
    expect(manifest.pages).toEqual({});
  });
});

describe('incremental builds', () => {
  let fixture: Fixture;

  afterEach(() => {
    cleanupFixture(fixture);
  });

  it('creates a .ssg-cache.json manifest on first build', () => {
    fixture = createFixture({ 'a.md': '---\ntitle: A\n---\n\nA body.' });

    const result = buildSiteIncremental(fixture.contentDir, fixture.outputDir, fixture.templatesDir);

    expect(result.stats.pagesBuilt).toBe(1);
    expect(result.stats.pagesSkipped).toBe(0);
    expect(existsSync(join(fixture.outputDir, CACHE_FILE_NAME))).toBe(true);
    expect(existsSync(join(fixture.outputDir, 'a.html'))).toBe(true);
    expect(existsSync(join(fixture.outputDir, 'index.html'))).toBe(true);
  });

  it('skips every page when nothing changed', () => {
    fixture = createFixture({
      'a.md': '---\ntitle: A\n---\n\nA body.',
      'b.md': '---\ntitle: B\n---\n\nB body.',
    });

    const first = buildSiteIncremental(fixture.contentDir, fixture.outputDir, fixture.templatesDir);
    expect(first.stats.pagesBuilt).toBe(2);
    expect(first.stats.pagesSkipped).toBe(0);

    const aBefore = readFileSync(join(fixture.outputDir, 'a.html'), 'utf8');
    const second = buildSiteIncremental(fixture.contentDir, fixture.outputDir, fixture.templatesDir);
    expect(second.stats.pagesBuilt).toBe(0);
    expect(second.stats.pagesSkipped).toBe(2);
    expect(second.stats.timeSavedMs).toBeGreaterThan(0);
    expect(readFileSync(join(fixture.outputDir, 'a.html'), 'utf8')).toBe(aBefore);
  });

  it('rebuilds only the changed page', () => {
    fixture = createFixture({
      'a.md': '---\ntitle: A\n---\n\nA body.',
      'b.md': '---\ntitle: B\n---\n\nB body.',
    });

    buildSiteIncremental(fixture.contentDir, fixture.outputDir, fixture.templatesDir);
    writeFileSync(join(fixture.contentDir, 'a.md'), '---\ntitle: A\n---\n\nA body changed.');

    const result = buildSiteIncremental(fixture.contentDir, fixture.outputDir, fixture.templatesDir);
    expect(result.stats.pagesBuilt).toBe(1);
    expect(result.stats.pagesSkipped).toBe(1);
    expect(readFileSync(join(fixture.outputDir, 'a.html'), 'utf8')).toContain('A body changed.');
    expect(readFileSync(join(fixture.outputDir, 'b.html'), 'utf8')).toContain('B body.');
  });

  it('rebuilds every page when a template changes', () => {
    fixture = createFixture(
      {
        'a.md': '---\ntitle: A\n---\n\nA body.',
        'b.md': '---\ntitle: B\n---\n\nB body.',
      },
      { 'default.hbs': 'OLD {{title}} {{{content}}}' }
    );

    buildSiteIncremental(fixture.contentDir, fixture.outputDir, fixture.templatesDir);
    writeFileSync(join(fixture.templatesDir, 'default.hbs'), 'NEW {{title}} {{{content}}}');

    const result = buildSiteIncremental(fixture.contentDir, fixture.outputDir, fixture.templatesDir);
    expect(result.stats.pagesBuilt).toBe(2);
    expect(result.stats.pagesSkipped).toBe(0);
    expect(readFileSync(join(fixture.outputDir, 'a.html'), 'utf8')).toContain('NEW');
    expect(readFileSync(join(fixture.outputDir, 'b.html'), 'utf8')).toContain('NEW');
  });

  it('does a full rebuild when clean is requested', () => {
    fixture = createFixture({ 'a.md': '---\ntitle: A\n---\n\nA body.' });

    buildSiteIncremental(fixture.contentDir, fixture.outputDir, fixture.templatesDir);
    const result = buildSiteIncremental(fixture.contentDir, fixture.outputDir, fixture.templatesDir, { clean: true });

    expect(result.stats.pagesBuilt).toBe(1);
    expect(result.stats.pagesSkipped).toBe(0);
  });

  it('does a full rebuild when the cache manifest is missing', () => {
    fixture = createFixture({ 'a.md': '---\ntitle: A\n---\n\nA body.' });

    buildSiteIncremental(fixture.contentDir, fixture.outputDir, fixture.templatesDir);
    rmSync(join(fixture.outputDir, CACHE_FILE_NAME));

    const result = buildSiteIncremental(fixture.contentDir, fixture.outputDir, fixture.templatesDir);
    expect(result.stats.pagesBuilt).toBe(1);
    expect(result.stats.pagesSkipped).toBe(0);
  });

  it('ignores a corrupted cache manifest', () => {
    fixture = createFixture({ 'a.md': '---\ntitle: A\n---\n\nA body.' });
    mkdirSync(fixture.outputDir, { recursive: true });
    writeFileSync(join(fixture.outputDir, CACHE_FILE_NAME), '{ not json');

    const result = buildSiteIncremental(fixture.contentDir, fixture.outputDir, fixture.templatesDir);
    expect(result.stats.pagesBuilt).toBe(1);
  });

  it('removes the stale output when a source file is deleted', () => {
    fixture = createFixture({
      'a.md': '---\ntitle: A\n---\n\nA body.',
      'b.md': '---\ntitle: B\n---\n\nB body.',
    });

    buildSiteIncremental(fixture.contentDir, fixture.outputDir, fixture.templatesDir);
    expect(existsSync(join(fixture.outputDir, 'b.html'))).toBe(true);

    rmSync(join(fixture.contentDir, 'b.md'));
    const result = buildSiteIncremental(fixture.contentDir, fixture.outputDir, fixture.templatesDir);

    expect(result.stats.pagesBuilt).toBe(0);
    expect(result.stats.pagesSkipped).toBe(1);
    expect(existsSync(join(fixture.outputDir, 'b.html'))).toBe(false);
  });

  it('caches parsed frontmatter and rendered html in the manifest', () => {
    fixture = createFixture({
      'post.md': '---\ntitle: Post\ndate: 2024-05-01\ntags: [a, b]\n---\n\nHello **world**.',
    });

    buildSiteIncremental(fixture.contentDir, fixture.outputDir, fixture.templatesDir);

    const manifest = JSON.parse(readFileSync(join(fixture.outputDir, CACHE_FILE_NAME), 'utf8'));
    const page = manifest.pages['post.md'];
    expect(page).toBeDefined();
    expect(page.sourceHash).toBe(hashFile(join(fixture.contentDir, 'post.md')));
    expect(page.frontmatter.title).toBe('Post');
    expect(page.frontmatter.date).toBe('2024-05-01T00:00:00.000Z');
    expect(page.frontmatter.tags).toEqual(['a', 'b']);
    expect(page.contentHtml).toContain('<strong>world</strong>');
    expect(page.html).toContain('<title>Post</title>');
  });

  it('reconstructs cached pages with identical output', () => {
    fixture = createFixture({ 'post.md': '---\ntitle: Post\n---\n\nBody.' });

    const first = buildSiteIncremental(fixture.contentDir, fixture.outputDir, fixture.templatesDir);
    expect(first.pages[0].html).toContain('<title>Post</title>');

    const second = buildSiteIncremental(fixture.contentDir, fixture.outputDir, fixture.templatesDir);
    expect(second.pages[0].html).toBe(first.pages[0].html);
    expect(second.pages[0].title).toBe('Post');
    expect(second.pages[0].cachedOutput).toBe(true);
  });

  it('keeps the plugin pipeline intact during incremental builds', () => {
    fixture = createFixture({ 'post.md': '---\ntitle: Post\n---\n\nBody.' });
    const order: string[] = [];
    const { createEngine } = require('../src/ssg') as typeof import('../src/ssg');
    const engine = createEngine({
      contentDir: fixture.contentDir,
      outputDir: fixture.outputDir,
      templatesDir: fixture.templatesDir,
      plugins: [
        {
          name: 'custom',
          beforeBuild: () => order.push('beforeBuild'),
          onFile: (page) => {
            order.push('onFile');
            page.title = 'Mutated';
            return page;
          },
          afterBuild: () => order.push('afterBuild'),
          onEnd: () => order.push('onEnd'),
        },
      ],
    });

    engine.start();
    const result = engine.buildIncremental();
    expect(result.pages[0].title).toBe('Mutated');
    expect(readFileSync(join(fixture.outputDir, 'post.html'), 'utf8')).toContain('<title>Mutated</title>');
    expect(order).toEqual(['beforeBuild', 'onFile', 'afterBuild', 'onEnd']);

    const second = engine.buildIncremental();
    expect(second.stats.pagesSkipped).toBe(1);
    expect(second.pages[0].title).toBe('Mutated');
  });
});

describe('incremental CLI', () => {
  let fixture: Fixture;

  afterEach(() => {
    if (fixture) cleanupFixture(fixture);
  });

  it('parses the --incremental and --clean flags', () => {
    const parsed = parseArgs(['build', '--incremental', '--clean']);
    expect(parsed?.command).toBe('build');
    expect((parsed?.options as BuildOptions).incremental).toBe(true);
    expect((parsed?.options as BuildOptions).clean).toBe(true);
  });

  it('rejects --incremental for the serve command', () => {
    expect(parseArgs(['serve', '--incremental'])).toBeNull();
  });

  it('runs an incremental build through the CLI and reports stats', () => {
    fixture = createFixture({ 'a.md': '---\ntitle: A\n---\n\nA body.' });

    const firstWrite = jest.spyOn(process.stdout, 'write').mockImplementation(() => true);
    const firstCode = run(['build', '--incremental', '--content', fixture.contentDir, '--output', fixture.outputDir]);
    const firstOutput = firstWrite.mock.calls.map((call) => String(call[0])).join('');
    firstWrite.mockRestore();

    expect(firstCode).toBe(0);
    expect(firstOutput).toContain('Built 1 page(s)');
    expect(firstOutput).toContain('skipped 0');

    const secondWrite = jest.spyOn(process.stdout, 'write').mockImplementation(() => true);
    const secondCode = run(['build', '--incremental', '--content', fixture.contentDir, '--output', fixture.outputDir]);
    const secondOutput = secondWrite.mock.calls.map((call) => String(call[0])).join('');
    secondWrite.mockRestore();

    expect(secondCode).toBe(0);
    expect(secondOutput).toContain('Built 0 page(s)');
    expect(secondOutput).toContain('skipped 1');
  });

  it('runs a clean incremental build through the CLI', () => {
    fixture = createFixture({ 'a.md': '---\ntitle: A\n---\n\nA body.' });

    run(['build', '--incremental', '--content', fixture.contentDir, '--output', fixture.outputDir]);
    const write = jest.spyOn(process.stdout, 'write').mockImplementation(() => true);
    const code = run(['build', '--incremental', '--clean', '--content', fixture.contentDir, '--output', fixture.outputDir]);
    const output = write.mock.calls.map((call) => String(call[0])).join('');
    write.mockRestore();

    expect(code).toBe(0);
    expect(output).toContain('Built 1 page(s)');
    expect(output).toContain('skipped 0');
  });

  it('keeps the plain build output unchanged', () => {
    fixture = createFixture({ 'a.md': '---\ntitle: A\n---\n\nA body.' });
    const write = jest.spyOn(process.stdout, 'write').mockImplementation(() => true);
    const code = run(['build', '--content', fixture.contentDir, '--output', fixture.outputDir]);
    const output = write.mock.calls.map((call) => String(call[0])).join('');
    write.mockRestore();

    expect(code).toBe(0);
    expect(output).toContain('Built 1 page(s) into');
  });
});

describe('buildSiteIncremental compatibility', () => {
  let fixture: Fixture;

  afterEach(() => {
    cleanupFixture(fixture);
  });

  it('produces the same output files as a plain build', () => {
    fixture = createFixture({
      'post.md': '---\ntitle: Post\ntags: [x]\n---\n\nHello **world**.',
    });

    buildSiteIncremental(fixture.contentDir, fixture.outputDir, fixture.templatesDir);

    expect(existsSync(join(fixture.outputDir, 'post.html'))).toBe(true);
    expect(existsSync(join(fixture.outputDir, 'index.html'))).toBe(true);
    const html = readFileSync(join(fixture.outputDir, 'post.html'), 'utf8');
    expect(html).toContain('<title>Post</title>');
    expect(html).toContain('<strong>world</strong>');
  });
});
