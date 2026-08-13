import { mkdtemp, mkdir, readFile, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { buildSite } from '../src/generator';
import { parseArguments } from '../src/cli';

describe('buildSite', () => {
  it('renders frontmatter, Markdown pages, and an index', async () => {
    const root = await mkdtemp(join(tmpdir(), 'ssg-'));
    const content = join(root, 'content');
    const output = join(root, 'output');
    await mkdir(join(content, 'guides'), { recursive: true });
    await writeFile(join(content, 'hello.md'), '---\ntitle: Hello World\ndate: 2026-08-13\ntags:\n  - intro\n  - welcome\n---\n\n# Welcome\n\nA **site** page.');
    await writeFile(join(content, 'guides', 'start.markdown'), '# Getting Started');

    const pages = await buildSite({ contentDir: content, outputDir: output });

    expect(pages.map((page) => page.outputPath)).toEqual(['guides/start.html', 'hello.html']);
    await expect(readFile(join(output, 'hello.html'), 'utf8')).resolves.toContain('<h1>Welcome</h1>');
    await expect(readFile(join(output, 'hello.html'), 'utf8')).resolves.toContain('Tags: intro, welcome');
    await expect(readFile(join(output, 'guides', 'start.html'), 'utf8')).resolves.toContain('<title>start</title>');
    await expect(readFile(join(output, 'index.html'), 'utf8')).resolves.toContain('href="guides/start.html"');
  });
});

describe('parseArguments', () => {
  it('accepts custom content and output directories', () => {
    expect(parseArguments(['--content', 'posts', '--output', 'public'])).toEqual({ contentDir: 'posts', outputDir: 'public' });
  });

  it('rejects invalid options', () => {
    expect(() => parseArguments(['--nope'])).toThrow('Unknown option: --nope');
  });
});
