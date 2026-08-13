import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { buildSite } from '../src/site.js';

describe('buildSite', () => {
  let directory: string;

  beforeEach(async () => {
    directory = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-'));
  });

  afterEach(async () => {
    await fs.rm(directory, { recursive: true, force: true });
  });

  it('renders frontmatter, markdown, nested pages, and an ordered index', async () => {
    const content = path.join(directory, 'content');
    const output = path.join(directory, 'dist');
    await fs.mkdir(path.join(content, 'guides'), { recursive: true });
    await fs.writeFile(path.join(content, 'welcome.md'), '---\ntitle: Welcome <Site>\ndate: 2025-01-02\ntags: [news, start]\n---\n# Hello\n\n**World**');
    await fs.writeFile(path.join(content, 'guides', 'install.md'), '---\ntitle: Install\ndate: 2025-02-03\n---\nInstallation text');

    const pages = await buildSite({ contentDir: content, outputDir: output });

    expect(pages.map((page) => page.title)).toEqual(['Install', 'Welcome <Site>']);
    await expect(fs.readFile(path.join(output, 'welcome.html'), 'utf8')).resolves.toContain('<h1>Welcome &lt;Site&gt;</h1>');
    await expect(fs.readFile(path.join(output, 'welcome.html'), 'utf8')).resolves.toContain('<strong>World</strong>');
    await expect(fs.readFile(path.join(output, 'guides', 'install.html'), 'utf8')).resolves.toContain('Installation text');
    await expect(fs.readFile(path.join(output, 'index.html'), 'utf8')).resolves.toContain('href="/guides/install.html"');
  });

  it('uses the filename as a title when frontmatter omits one', async () => {
    const content = path.join(directory, 'content');
    await fs.mkdir(content);
    await fs.writeFile(path.join(content, 'untitled.md'), 'Plain text');

    const pages = await buildSite({ contentDir: content, outputDir: path.join(directory, 'dist') });

    expect(pages[0].title).toBe('untitled');
  });
});
