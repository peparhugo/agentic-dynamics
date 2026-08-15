import { mkdtemp, readFile, rm, writeFile, mkdir } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { buildSite } from './build';

describe('buildSite', () => {
  let root: string;

  beforeEach(async () => { root = await mkdtemp(join(tmpdir(), 'ssg-')); });
  afterEach(async () => { await rm(root, { recursive: true, force: true }); });

  it('writes a page per markdown file and an index', async () => {
    const content = join(root, 'content');
    const output = join(root, 'dist');
    await mkdir(join(content, 'guides'), { recursive: true });
    await writeFile(join(content, 'first.md'), '---\ntitle: First\ndate: 2026-01-02\ntags: alpha, beta\n---\n# First body');
    await writeFile(join(content, 'guides', 'second.md'), '# Second body');

    const pages = await buildSite(content, output);

    expect(pages).toHaveLength(2);
    expect(await readFile(join(output, 'first.html'), 'utf8')).toContain('<h1>First</h1>');
    expect(await readFile(join(output, 'guides', 'second.html'), 'utf8')).toContain('<h1>second</h1>');
    const index = await readFile(join(output, 'index.html'), 'utf8');
    expect(index).toContain('href="first.html"');
    expect(index).toContain('href="guides/second.html"');
  });
});
