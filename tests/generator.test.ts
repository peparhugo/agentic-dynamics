import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { buildSite, parsePage } from '../src/generator';

describe('parsePage', () => {
  it('merges simple YAML frontmatter and renders Markdown', () => {
    const page = parsePage('---\ntitle: Hello world\ndate: 2026-08-15\ntags: [typescript, static]\n---\n# Welcome\n\nText', 'hello.md');

    expect(page).toMatchObject({ title: 'Hello world', date: '2026-08-15', tags: ['typescript', 'static'], slug: 'hello' });
    expect(page.html).toContain('<h1>Welcome</h1>');
  });

  it('uses the filename and empty tags when frontmatter is absent', () => {
    expect(parsePage('A paragraph', 'notes.md')).toMatchObject({ title: 'notes', tags: [], slug: 'notes' });
  });
});

describe('buildSite', () => {
  let root: string;

  beforeEach(() => { root = mkdtempSync(join(tmpdir(), 'ssg-')); });
  afterEach(() => { rmSync(root, { recursive: true, force: true }); });

  it('writes each page and an index to the selected output directory', () => {
    const content = join(root, 'content');
    const output = join(root, 'site');
    mkdirSync(content);
    writeFileSync(join(content, 'first.md'), '---\ntitle: First post\ndate: 2026-01-02\n---\n# First');
    writeFileSync(join(content, 'second.md'), '# Second');

    expect(buildSite({ contentDir: content, outputDir: output })).toHaveLength(2);
    expect(readFileSync(join(output, 'first.html'), 'utf8')).toContain('<h1>First post</h1>');
    const index = readFileSync(join(output, 'index.html'), 'utf8');
    expect(index).toContain('href="first.html"');
    expect(index).toContain('First post');
  });
});
