import { mkdtemp, readFile, rm, writeFile, mkdir } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { buildSite, parseYamlFrontmatter } from '../src/generator';

describe('static site generator', () => {
  let directory: string;

  beforeEach(async () => { directory = await mkdtemp(join(tmpdir(), 'ssg-')); });
  afterEach(async () => { await rm(directory, { recursive: true, force: true }); });

  it('extracts a simple YAML frontmatter block', () => {
    expect(parseYamlFrontmatter('---\ntitle: Hello\ntags: [news, typescript]\n---\n# Body')).toEqual({ data: { title: 'Hello', tags: ['news', 'typescript'] }, content: '# Body' });
  });

  it('builds page files and an index from Markdown content', async () => {
    const content = join(directory, 'content');
    const output = join(directory, 'public');
    await mkdir(join(content, 'guides'), { recursive: true });
    await writeFile(join(content, 'welcome.md'), '---\ntitle: Welcome\ndate: 2026-08-15\ntags: [news, updates]\n---\n# Hello\n\nThis is **Markdown**.');
    await writeFile(join(content, 'guides', 'start.md'), '---\ntitle: Getting Started\n---\nA guide.');

    const pages = await buildSite({ contentDir: content, outputDir: output });
    const page = await readFile(join(output, 'welcome.html'), 'utf8');
    const index = await readFile(join(output, 'index.html'), 'utf8');

    expect(pages).toHaveLength(2);
    expect(page).toContain('<h1>Welcome</h1>');
    expect(page).toContain('<strong>Markdown</strong>');
    expect(page).toContain('Tags: news, updates');
    expect(await readFile(join(output, 'guides', 'start.html'), 'utf8')).toContain('<h1>Getting Started</h1>');
    expect(index).toContain('href="welcome.html"');
    expect(index).toContain('href="guides/start.html"');
  });
});
