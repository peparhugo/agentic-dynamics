import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { buildSite } from '../src/generator.js';
import { parseArguments } from '../src/cli.js';

describe('static site generator', () => {
  let workspace: string;

  beforeEach(async () => {
    workspace = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-'));
    await fs.mkdir(path.join(workspace, 'content'));
  });

  afterEach(async () => {
    await fs.rm(workspace, { recursive: true, force: true });
  });

  it('renders markdown pages and an index with frontmatter', async () => {
    await fs.writeFile(path.join(workspace, 'content', 'hello.md'), '---\ntitle: Hello World\ndate: 2026-08-13\ntags:\n  - news\n  - update\n---\n\n# Welcome\n\nThis is **important**.');
    const pages = await buildSite({ contentDir: path.join(workspace, 'content'), outputDir: path.join(workspace, 'output') });

    expect(pages).toEqual([expect.objectContaining({ title: 'Hello World', date: '2026-08-13', tags: ['news', 'update'], slug: 'hello' })]);
    await expect(fs.readFile(path.join(workspace, 'output', 'hello.html'), 'utf8')).resolves.toContain('<strong>important</strong>');
    await expect(fs.readFile(path.join(workspace, 'output', 'index.html'), 'utf8')).resolves.toContain('Hello World');
  });

  it('parses build CLI options and rejects invalid commands', () => {
    expect(parseArguments(['build', '--content', 'posts', '--output', 'public'])).toEqual({ contentDir: 'posts', outputDir: 'public' });
    expect(() => parseArguments(['serve'])).toThrow('Usage:');
  });
});
