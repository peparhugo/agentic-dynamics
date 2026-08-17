import { promises as fs } from 'fs';
import os from 'os';
import path from 'path';
import { buildSite } from '../src/generate';

async function makeTempDir(): Promise<string> {
  return fs.mkdtemp(path.join(os.tmpdir(), 'ssg-incremental-test-'));
}

describe('incremental builds', () => {
  it('performs a full build when no cache manifest exists', async () => {
    const content = await makeTempDir();
    const output = await makeTempDir();
    await fs.writeFile(path.join(content, 'a.md'), '# A\n');
    await fs.writeFile(path.join(content, 'b.md'), '# B\n');

    const result = await buildSite(content, output, undefined, { incremental: true });

    expect(result.stats.pagesBuilt).toBe(2);
    expect(result.stats.pagesSkipped).toBe(0);

    const cache = JSON.parse(await fs.readFile(path.join(output, '.ssg-cache.json'), 'utf8'));
    expect(cache.pages).toHaveProperty('a');
    expect(cache.pages).toHaveProperty('b');
  });

  it('skips unchanged pages on the second build', async () => {
    const content = await makeTempDir();
    const output = await makeTempDir();
    await fs.writeFile(path.join(content, 'a.md'), '# A\n');
    await fs.writeFile(path.join(content, 'b.md'), '# B\n');

    await buildSite(content, output, undefined, { incremental: true });
    const second = await buildSite(content, output, undefined, { incremental: true });

    expect(second.stats.pagesBuilt).toBe(0);
    expect(second.stats.pagesSkipped).toBe(2);
  });

  it('rebuilds only the changed page', async () => {
    const content = await makeTempDir();
    const output = await makeTempDir();
    await fs.writeFile(path.join(content, 'a.md'), '# A\n');
    await fs.writeFile(path.join(content, 'b.md'), '# B\n');
    await buildSite(content, output, undefined, { incremental: true });

    await fs.writeFile(path.join(content, 'a.md'), '# A changed\n');
    const result = await buildSite(content, output, undefined, { incremental: true });

    expect(result.stats.pagesBuilt).toBe(1);
    expect(result.stats.pagesSkipped).toBe(1);

    const aHtml = await fs.readFile(path.join(output, 'a.html'), 'utf8');
    expect(aHtml).toContain('A changed');
    const bHtml = await fs.readFile(path.join(output, 'b.html'), 'utf8');
    expect(bHtml).toContain('<h1>B</h1>');
  });

  it('rebuilds all pages when a template changes', async () => {
    const content = await makeTempDir();
    const output = await makeTempDir();
    const templates = await makeTempDir();
    await fs.writeFile(path.join(templates, 'page.hbs'), '<p>{{title}}</p>');
    await fs.writeFile(path.join(content, 'a.md'), '---\ntitle: A\ntemplate: page\n---\n# A\n');
    await fs.writeFile(path.join(content, 'b.md'), '---\ntitle: B\ntemplate: page\n---\n# B\n');

    await buildSite(content, output, templates, { incremental: true });

    await fs.writeFile(path.join(templates, 'page.hbs'), '<p>CHANGED {{title}}</p>');
    const result = await buildSite(content, output, templates, { incremental: true });

    expect(result.stats.pagesBuilt).toBe(2);
    expect(result.stats.pagesSkipped).toBe(0);

    const aHtml = await fs.readFile(path.join(output, 'a.html'), 'utf8');
    expect(aHtml).toContain('CHANGED A');
  });

  it('forces a full rebuild with the clean flag', async () => {
    const content = await makeTempDir();
    const output = await makeTempDir();
    await fs.writeFile(path.join(content, 'a.md'), '# A\n');
    await fs.writeFile(path.join(content, 'b.md'), '# B\n');

    await buildSite(content, output, undefined, { incremental: true });
    const result = await buildSite(content, output, undefined, { incremental: true, clean: true });

    expect(result.stats.pagesBuilt).toBe(2);
    expect(result.stats.pagesSkipped).toBe(0);
  });

  it('restores a deleted output file from the cache without re-rendering', async () => {
    const content = await makeTempDir();
    const output = await makeTempDir();
    await fs.writeFile(path.join(content, 'a.md'), '# A\n');

    await buildSite(content, output, undefined, { incremental: true });
    await fs.unlink(path.join(output, 'a.html'));

    const result = await buildSite(content, output, undefined, { incremental: true });

    expect(result.stats.pagesSkipped).toBe(1);
    const aHtml = await fs.readFile(path.join(output, 'a.html'), 'utf8');
    expect(aHtml).toContain('<h1>A</h1>');
  });

  it('reuses cached frontmatter metadata when skipping', async () => {
    const content = await makeTempDir();
    const output = await makeTempDir();
    await fs.writeFile(
      path.join(content, 'a.md'),
      '---\ntitle: Cached Title\ntags: [x, y]\n---\n# A\n'
    );

    await buildSite(content, output, undefined, { incremental: true });
    const result = await buildSite(content, output, undefined, { incremental: true });

    expect(result.stats.pagesSkipped).toBe(1);
    expect(result.pages[0].title).toBe('Cached Title');
    expect(result.pages[0].tags).toEqual(['x', 'y']);
  });

  it('reports zero saved time when nothing can be skipped', async () => {
    const content = await makeTempDir();
    const output = await makeTempDir();
    await fs.writeFile(path.join(content, 'a.md'), '# A\n');

    const result = await buildSite(content, output, undefined, { incremental: true });

    expect(result.stats.timeSavedMs).toBe(0);
  });
});
