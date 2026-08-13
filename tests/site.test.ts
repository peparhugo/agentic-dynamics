import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync, mkdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { buildSite } from '../src/site';

describe('buildSite', () => {
  let workspace: string;

  beforeEach(() => {
    workspace = mkdtempSync(join(tmpdir(), 'ssg-test-'));
  });

  afterEach(() => {
    rmSync(workspace, { recursive: true, force: true });
  });

  it('renders Markdown, frontmatter, and an index page', () => {
    const content = join(workspace, 'content');
    const output = join(workspace, 'public');
    mkdirSync(content);
    writeFileSync(join(content, 'welcome.md'), `---

    const pages = buildSite({ contentDir: content, outputDir: output });

    expect(pages).toHaveLength(1);
    expect(readFileSync(join(output, 'welcome.html'), 'utf8')).toContain('<h1>Hello</h1>');
    expect(readFileSync(join(output, 'welcome.html'), 'utf8')).toContain('<title>Welcome &lt;Home&gt;</title>');
    expect(readFileSync(join(output, 'welcome.html'), 'utf8')).toContain('<span>news</span>');
    expect(readFileSync(join(output, 'welcome.html'), 'utf8')).toContain('<time datetime="2025-01-02">2025-01-02</time>');
    expect(readFileSync(join(output, 'index.html'), 'utf8')).toContain('<a href="welcome.html">Welcome &lt;Home&gt;</a>');
  });

  it('preserves nested Markdown paths and uses a filename title when absent', () => {
    const content = join(workspace, 'content');
    const output = join(workspace, 'dist');
    mkdirSync(join(content, 'guides'), { recursive: true });
    writeFileSync(join(content, 'guides', 'install.md'), 'Install instructions');

    const pages = buildSite({ contentDir: content, outputDir: output });

    expect(pages[0]).toMatchObject({ title: 'guides/install', url: 'guides/install.html' });
    expect(existsSync(join(output, 'guides', 'install.html'))).toBe(true);
    expect(readFileSync(join(output, 'index.html'), 'utf8')).toContain('href="guides/install.html"');
  });

  it('fails with a clear error for a missing content directory', () => {
    expect(() => buildSite({ contentDir: join(workspace, 'missing') })).toThrow('Content directory does not exist');
  });
});
