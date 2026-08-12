import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { buildSite, buildSiteDetailed } from '../src/build';
import { CACHE_FILE_NAME, readCache } from '../src/cache';
import type { BuildResult } from '../src/build';

describe('incremental builds', () => {
  let tmp: string;

  beforeEach(() => {
    tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-inc-'));
  });

  afterEach(() => {
    fs.rmSync(tmp, { recursive: true, force: true });
  });

  const contentDir = (): string => path.join(tmp, 'content');
  const templatesDir = (): string => path.join(tmp, 'templates');
  const outputDir = (): string => path.join(tmp, 'dist');

  function writeContent(relPath: string, content: string): string {
    const full = path.join(contentDir(), relPath);
    fs.mkdirSync(path.dirname(full), { recursive: true });
    fs.writeFileSync(full, content, 'utf8');
    return full;
  }

  function writeTemplate(relPath: string, content: string): string {
    const full = path.join(templatesDir(), relPath);
    fs.mkdirSync(path.dirname(full), { recursive: true });
    fs.writeFileSync(full, content, 'utf8');
    return full;
  }

  function build(incremental = false): Promise<BuildResult> {
    return buildSiteDetailed({
      contentDir: contentDir(),
      outputDir: outputDir(),
      siteTitle: 'Inc Site',
      templatesDir: templatesDir(),
      incremental,
    });
  }

  function expectStats(result: BuildResult, built: number, skipped: number): void {
    expect(result.stats.built).toBe(built);
    expect(result.stats.skipped).toBe(skipped);
    expect(result.stats.total).toBe(built + skipped);
  }

  it('writes a cache manifest on the first build', async () => {
    writeContent('a.md', '---\ntitle: A\n---\n\n# A');
    await build(false);

    const cache = readCache(outputDir());
    expect(cache).not.toBeNull();
    expect(cache!.pages['a.md'].html).toContain('<h1>A</h1>');
    expect(cache!.pages['a.md'].data.title).toBe('A');
    expect(fs.existsSync(path.join(outputDir(), CACHE_FILE_NAME))).toBe(true);
  });

  it('skips every unchanged page on an incremental rebuild', async () => {
    writeContent('a.md', '---\ntitle: A\n---\n\n# A');
    writeContent('b.md', '---\ntitle: B\n---\n\n# B');

    const first = await build(false);
    expectStats(first, 2, 0);

    const second = await build(true);
    expectStats(second, 0, 2);
    expect(second.stats.timeSavedMs).toBeGreaterThan(0);

    const a = fs.readFileSync(path.join(outputDir(), 'a.html'), 'utf8');
    const b = fs.readFileSync(path.join(outputDir(), 'b.html'), 'utf8');
    expect(a).toContain('<h1>A</h1>');
    expect(b).toContain('<h1>B</h1>');
  });

  it('only rebuilds the page whose source changed', async () => {
    writeContent('a.md', '---\ntitle: A\n---\n\n# A');
    writeContent('b.md', '---\ntitle: B\n---\n\n# B');
    await build(false);

    writeContent('b.md', '---\ntitle: B Updated\n---\n\n# B updated body');

    const result = await build(true);
    expectStats(result, 1, 1);

    const b = fs.readFileSync(path.join(outputDir(), 'b.html'), 'utf8');
    expect(b).toContain('<h1>B Updated</h1>');
    expect(b).toContain('<h1>B updated body</h1>');

    const a = fs.readFileSync(path.join(outputDir(), 'a.html'), 'utf8');
    expect(a).toContain('<h1>A</h1>');
  });

  it('builds only new pages when files are added', async () => {
    writeContent('a.md', '---\ntitle: A\n---\n\n# A');
    await build(false);

    writeContent('b.md', '---\ntitle: B\n---\n\n# B');

    const result = await build(true);
    expectStats(result, 1, 1);
    expect(fs.existsSync(path.join(outputDir(), 'b.html'))).toBe(true);

    const index = fs.readFileSync(path.join(outputDir(), 'index.html'), 'utf8');
    expect(index).toContain('<a href="b.html">B</a>');
  });

  it('removes output and cache entries for deleted source files', async () => {
    writeContent('a.md', '---\ntitle: A\n---\n\n# A');
    writeContent('b.md', '---\ntitle: B\n---\n\n# B');
    await build(false);

    fs.rmSync(path.join(contentDir(), 'a.md'));

    const result = await build(true);
    expectStats(result, 0, 1);
    expect(fs.existsSync(path.join(outputDir(), 'a.html'))).toBe(false);
    expect(fs.existsSync(path.join(outputDir(), 'b.html'))).toBe(true);

    const cache = readCache(outputDir());
    expect(cache!.pages['a.md']).toBeUndefined();
    expect(cache!.pages['b.md']).toBeDefined();
  });

  it('rebuilds only pages that use a changed template', async () => {
    writeTemplate('default.hbs', '<main class="base">\n{{{html}}}\n</main>');
    writeTemplate('post.hbs', '<article class="post">\n{{{html}}}\n</article>');
    writeContent('a.md', '---\ntitle: A\n---\n\n# A');
    writeContent('b.md', '---\ntitle: B\ntemplate: post\n---\n\n# B');

    await build(false);

    writeTemplate('post.hbs', '<article class="post-v2">\n{{{html}}}\n</article>');

    const result = await build(true);
    expectStats(result, 1, 1);

    const a = fs.readFileSync(path.join(outputDir(), 'a.html'), 'utf8');
    const b = fs.readFileSync(path.join(outputDir(), 'b.html'), 'utf8');
    expect(a).toContain('class="base"');
    expect(a).not.toContain('class="post');
    expect(b).toContain('class="post-v2"');
    expect(b).not.toContain('class="post"');
  });

  it('rebuilds pages when a template they depend on is added', async () => {
    writeContent('a.md', '---\ntitle: A\n---\n\n# A');
    await build(false);

    writeTemplate('default.hbs', '<main class="now-templated">\n{{{html}}}\n</main>');

    const result = await build(true);
    expectStats(result, 1, 0);

    const a = fs.readFileSync(path.join(outputDir(), 'a.html'), 'utf8');
    expect(a).toContain('class="now-templated"');
  });

  it('rebuilds when a shared partial changes', async () => {
    writeTemplate('partials/header.hbs', '<header class="v1">Old</header>');
    writeTemplate('default.hbs', '{{> header}}\n{{{html}}}');
    writeContent('a.md', '---\ntitle: A\n---\n\n# A');
    writeContent('b.md', '---\ntitle: B\n---\n\n# B');

    await build(false);

    writeTemplate('partials/header.hbs', '<header class="v2">New</header>');

    const result = await build(true);
    expectStats(result, 2, 0);

    const a = fs.readFileSync(path.join(outputDir(), 'a.html'), 'utf8');
    const b = fs.readFileSync(path.join(outputDir(), 'b.html'), 'utf8');
    expect(a).toContain('class="v2"');
    expect(b).toContain('class="v2"');
  });

  it('does a clean build when the cache is missing', async () => {
    writeContent('a.md', '---\ntitle: A\n---\n\n# A');
    writeContent('b.md', '---\ntitle: B\n---\n\n# B');
    await build(false);

    fs.rmSync(path.join(outputDir(), CACHE_FILE_NAME));

    const result = await build(true);
    expectStats(result, 2, 0);
  });

  it('does a clean build when the --clean flag is passed', async () => {
    writeContent('a.md', '---\ntitle: A\n---\n\n# A');
    writeContent('b.md', '---\ntitle: B\n---\n\n# B');
    await build(false);

    const result = await buildSiteDetailed({
      contentDir: contentDir(),
      outputDir: outputDir(),
      siteTitle: 'Inc Site',
      templatesDir: templatesDir(),
      incremental: true,
      clean: true,
    });
    expectStats(result, 2, 0);
  });

  it('falls back to a full build when site config changes', async () => {
    writeContent('a.md', '---\ntitle: A\n---\n\n# A');
    await build(false);

    const result = await buildSiteDetailed({
      contentDir: contentDir(),
      outputDir: outputDir(),
      siteTitle: 'Different Title',
      templatesDir: templatesDir(),
      incremental: true,
    });
    expectStats(result, 1, 0);

    const index = fs.readFileSync(path.join(outputDir(), 'index.html'), 'utf8');
    expect(index).toContain('<title>Different Title</title>');
  });

  it('produces identical output to a full build after incremental reuse', async () => {
    writeContent('a.md', '---\ntitle: A\n---\n\n# A body');
    writeContent('b.md', '---\ntitle: B\n---\n\n# B body');

    const full = await build(false);
    const fullA = fs.readFileSync(path.join(outputDir(), 'a.html'), 'utf8');
    const fullB = fs.readFileSync(path.join(outputDir(), 'b.html'), 'utf8');
    expect(full.pages).toHaveLength(2);

    writeContent('b.md', '---\ntitle: B\n---\n\n# B body changed');

    const inc = await build(true);
    expectStats(inc, 1, 1);

    const incA = fs.readFileSync(path.join(outputDir(), 'a.html'), 'utf8');
    const incB = fs.readFileSync(path.join(outputDir(), 'b.html'), 'utf8');
    expect(incA).toBe(fullA);
    expect(incB).not.toBe(fullB);
  });

  it('keeps buildSite returning the pages array for backwards compatibility', async () => {
    writeContent('a.md', '---\ntitle: A\n---\n\n# A');
    const pages = await buildSite({
      contentDir: contentDir(),
      outputDir: outputDir(),
      siteTitle: 'Inc Site',
      templatesDir: templatesDir(),
    });
    expect(Array.isArray(pages)).toBe(true);
    expect(pages).toHaveLength(1);
    expect(pages[0].slug).toBe('a');
  });

  it('rebuilds a page when its frontmatter template selection changes', async () => {
    writeTemplate('default.hbs', '<main class="base">\n{{{html}}}\n</main>');
    writeTemplate('post.hbs', '<article class="post">\n{{{html}}}\n</article>');
    writeContent('a.md', '---\ntitle: A\n---\n\n# A');

    await build(false);

    writeContent('a.md', '---\ntitle: A\ntemplate: post\n---\n\n# A');

    const result = await build(true);
    expectStats(result, 1, 0);

    const a = fs.readFileSync(path.join(outputDir(), 'a.html'), 'utf8');
    expect(a).toContain('class="post"');
  });

  it('caches parsed frontmatter so skipped pages keep their metadata', async () => {
    writeContent('a.md', '---\ntitle: Cached Title\ndate: 2024-01-01\ntags:\n  - one\n  - two\n---\n\n# A');
    await build(false);

    const result = await build(true);
    expectStats(result, 0, 1);
    expect(result.pages[0].data.title).toBe('Cached Title');
    expect(result.pages[0].data.date).toBe('2024-01-01');
    expect(result.pages[0].data.tags).toEqual(['one', 'two']);
  });
});
