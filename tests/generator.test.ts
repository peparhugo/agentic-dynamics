import { mkdtemp, mkdir, readFile, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { buildSite } from '../src/generator';
import { parseArguments } from '../src/cli';

describe('static site generator', () => {
  it('renders Markdown pages and a frontmatter-powered index', async () => {
    const root = await mkdtemp(join(tmpdir(), 'ssg-'));
    const content = join(root, 'content');
    const output = join(root, 'public');
    await mkdir(join(content, 'guides'), { recursive: true });
    await writeFile(join(content, 'welcome.md'), '---\ntitle: Welcome\ndate: 2026-08-13\ntags:\n  - news\n---\n\n# Hello\n\nA **site**.\n');
    await writeFile(join(content, 'guides', 'start.md'), '# Start here\n');

    const pages = await buildSite({ content, output });

    expect(pages.map((page) => page.slug)).toEqual(['guides/start', 'welcome']);
    await expect(readFile(join(output, 'welcome.html'), 'utf8')).resolves.toContain('<strong>site</strong>');
    await expect(readFile(join(output, 'guides', 'start.html'), 'utf8')).resolves.toContain('<h1>start</h1>');
    const index = await readFile(join(output, 'index.html'), 'utf8');
    expect(index).toContain('href="/welcome.html">Welcome</a>');
    expect(index).toContain('href="/guides/start.html">start</a>');
  });

  it('parses build directory options', () => {
    expect(parseArguments(['--content', 'posts', '--output', 'site'])).toEqual({ content: 'posts', output: 'site' });
    expect(() => parseArguments(['--content'])).toThrow('--content requires a directory');
  });
});
