import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { buildSite } from './site';

function makeTmpDir(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

describe('buildSite', () => {
  let contentDir: string;
  let outputDir: string;

  beforeEach(() => {
    contentDir = makeTmpDir('ssg-content-');
    outputDir = makeTmpDir('ssg-output-');
  });

  afterEach(() => {
    fs.rmSync(contentDir, { recursive: true, force: true });
    fs.rmSync(outputDir, { recursive: true, force: true });
  });

  it('generates an HTML file per markdown page', () => {
    fs.writeFileSync(
      path.join(contentDir, 'hello.md'),
      '---\ntitle: Hello\ndate: 2026-01-01\ntags: [a, b]\n---\n\n# Hi there\n'
    );
    fs.writeFileSync(
      path.join(contentDir, 'second.md'),
      '---\ntitle: Second Page\n---\n\nSome content.\n'
    );

    const result = buildSite({ contentDir, outputDir });

    expect(result.pages).toHaveLength(2);
    expect(fs.existsSync(path.join(outputDir, 'hello.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'second.html'))).toBe(true);

    const helloHtml = fs.readFileSync(path.join(outputDir, 'hello.html'), 'utf-8');
    expect(helloHtml).toContain('<h1>Hello</h1>');
    expect(helloHtml).toContain('Hi there');
    expect(helloHtml).toContain('a');
    expect(helloHtml).toContain('b');
  });

  it('generates an index.html listing all pages', () => {
    fs.writeFileSync(path.join(contentDir, 'one.md'), '---\ntitle: One\n---\nBody one.');
    fs.writeFileSync(path.join(contentDir, 'two.md'), '---\ntitle: Two\n---\nBody two.');

    buildSite({ contentDir, outputDir });

    const indexPath = path.join(outputDir, 'index.html');
    expect(fs.existsSync(indexPath)).toBe(true);

    const indexHtml = fs.readFileSync(indexPath, 'utf-8');
    expect(indexHtml).toContain('One');
    expect(indexHtml).toContain('Two');
    expect(indexHtml).toContain('href="one.html"');
    expect(indexHtml).toContain('href="two.html"');
  });

  it('falls back to a title derived from the filename when frontmatter has none', () => {
    fs.writeFileSync(path.join(contentDir, 'my-cool-post.md'), 'No frontmatter here.');

    const result = buildSite({ contentDir, outputDir });

    expect(result.pages[0].title).toBe('My Cool Post');
  });

  it('supports nested content directories', () => {
    fs.mkdirSync(path.join(contentDir, 'posts'));
    fs.writeFileSync(
      path.join(contentDir, 'posts', 'nested.md'),
      '---\ntitle: Nested Post\n---\nNested body.'
    );

    const result = buildSite({ contentDir, outputDir });

    expect(result.pages[0].outputPath).toBe('posts/nested.html');
    expect(fs.existsSync(path.join(outputDir, 'posts', 'nested.html'))).toBe(true);
  });

  it('throws a clear error when the content directory does not exist', () => {
    const missingDir = path.join(contentDir, 'does-not-exist');
    expect(() => buildSite({ contentDir: missingDir, outputDir })).toThrow(/not found/i);
  });
});
