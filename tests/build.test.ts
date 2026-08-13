import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { build } from '../src/build';

function makeTempDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-build-'));
}

describe('build', () => {
  let root: string;
  let contentDir: string;
  let outputDir: string;

  beforeEach(() => {
    root = makeTempDir();
    contentDir = path.join(root, 'content');
    outputDir = path.join(root, 'dist');
    fs.mkdirSync(contentDir);
  });

  afterEach(() => {
    fs.rmSync(root, { recursive: true, force: true });
  });

  it('generates an html file per markdown page plus an index', () => {
    fs.writeFileSync(
      path.join(contentDir, 'first.md'),
      '---\ntitle: First\ndate: 2026-01-01\n---\n\nFirst body.\n'
    );
    fs.writeFileSync(
      path.join(contentDir, 'second.md'),
      '---\ntitle: Second\ndate: 2026-02-01\n---\n\nSecond body.\n'
    );

    const result = build({ contentDir, outputDir });

    expect(result.pages).toHaveLength(2);
    expect(fs.existsSync(path.join(outputDir, 'index.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'first.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'second.html'))).toBe(true);

    const indexHtml = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf-8');
    expect(indexHtml).toContain('href="first.html"');
    expect(indexHtml).toContain('href="second.html"');

    const firstHtml = fs.readFileSync(path.join(outputDir, 'first.html'), 'utf-8');
    expect(firstHtml).toContain('First body.');
  });

  it('creates the output directory if it does not exist', () => {
    fs.writeFileSync(path.join(contentDir, 'only.md'), '# Only page');

    expect(fs.existsSync(outputDir)).toBe(false);
    build({ contentDir, outputDir });
    expect(fs.existsSync(outputDir)).toBe(true);
  });

  it('produces an empty index when there is no markdown content', () => {
    const result = build({ contentDir, outputDir });
    expect(result.pages).toHaveLength(0);
    expect(fs.existsSync(path.join(outputDir, 'index.html'))).toBe(true);
  });

  it('throws when the content directory does not exist', () => {
    expect(() => build({ contentDir: path.join(root, 'missing'), outputDir })).toThrow(
      /Content directory not found/
    );
  });

  it('throws when two pages resolve to the same slug', () => {
    fs.writeFileSync(path.join(contentDir, 'My Post.md'), '# One');
    fs.writeFileSync(path.join(contentDir, 'my-post.md'), '# Two');

    expect(() => build({ contentDir, outputDir })).toThrow(/Duplicate page slug/);
  });
});
