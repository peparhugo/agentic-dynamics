import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { build } from './build';

function makeTempDir(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

describe('build', () => {
  let contentDir: string;
  let outputDir: string;

  beforeEach(() => {
    contentDir = makeTempDir('ssg-content-');
    outputDir = makeTempDir('ssg-output-');
  });

  afterEach(() => {
    fs.rmSync(contentDir, { recursive: true, force: true });
    fs.rmSync(outputDir, { recursive: true, force: true });
  });

  it('throws a clear error when the content directory does not exist', () => {
    expect(() => build({ contentDir: path.join(contentDir, 'missing'), outputDir })).toThrow(
      /Content directory not found/
    );
  });

  it('generates an HTML file per markdown page plus an index', () => {
    fs.writeFileSync(
      path.join(contentDir, 'first.md'),
      '---\ntitle: First Post\ndate: 2026-01-02\ntags: [x]\n---\n\n# First\n\nHello.'
    );
    fs.writeFileSync(
      path.join(contentDir, 'second.md'),
      '---\ntitle: Second Post\ndate: 2026-01-05\n---\n\n# Second\n\nWorld.'
    );

    const result = build({ contentDir, outputDir, siteTitle: 'Test Site' });

    expect(result.pages).toHaveLength(2);
    expect(fs.existsSync(path.join(outputDir, 'first.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'second.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'index.html'))).toBe(true);

    const indexHtml = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf-8');
    expect(indexHtml).toContain('Test Site');
    expect(indexHtml).toContain('First Post');
    expect(indexHtml).toContain('Second Post');

    const firstHtml = fs.readFileSync(path.join(outputDir, 'first.html'), 'utf-8');
    expect(firstHtml).toContain('<h1>First</h1>');
    expect(firstHtml).toContain('Hello.');
  });

  it('sorts pages by date descending, newest first, in the index', () => {
    fs.writeFileSync(path.join(contentDir, 'old.md'), '---\ntitle: Old\ndate: 2020-01-01\n---\nOld content');
    fs.writeFileSync(path.join(contentDir, 'new.md'), '---\ntitle: New\ndate: 2026-01-01\n---\nNew content');

    const result = build({ contentDir, outputDir });
    expect(result.pages.map((p) => p.frontmatter.title)).toEqual(['New', 'Old']);
  });

  it('supports nested content directories and mirrors the structure in dist', () => {
    fs.mkdirSync(path.join(contentDir, 'posts'));
    fs.writeFileSync(
      path.join(contentDir, 'posts', 'nested.md'),
      '---\ntitle: Nested Post\n---\nNested content'
    );

    const result = build({ contentDir, outputDir });
    expect(result.pages[0].slug).toBe('posts/nested');
    expect(fs.existsSync(path.join(outputDir, 'posts', 'nested.html'))).toBe(true);
  });

  it('derives a title from the filename when frontmatter has none', () => {
    fs.writeFileSync(path.join(contentDir, 'no-frontmatter.md'), '# Just Content\n\nNo frontmatter at all.');
    const result = build({ contentDir, outputDir });
    expect(result.pages[0].frontmatter.title).toBe('No Frontmatter');
  });

  it('cleans previously generated output before rebuilding', () => {
    fs.writeFileSync(path.join(outputDir, 'stale.html'), 'stale');
    fs.writeFileSync(path.join(contentDir, 'page.md'), '---\ntitle: Page\n---\nContent');

    build({ contentDir, outputDir });

    expect(fs.existsSync(path.join(outputDir, 'stale.html'))).toBe(false);
  });

  it('writes a stylesheet used by the generated pages', () => {
    fs.writeFileSync(path.join(contentDir, 'page.md'), '---\ntitle: Page\n---\nContent');
    build({ contentDir, outputDir });
    expect(fs.existsSync(path.join(outputDir, 'style.css'))).toBe(true);
  });
});
