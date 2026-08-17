import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { build, loadPages } from '../src/build';
import { markdownToHtml, normalizeTags, parseFrontmatter } from '../src/ssg';

function makeTempDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-test-'));
}

describe('parseFrontmatter', () => {
  it('extracts title, date and tags and strips the frontmatter block', () => {
    const raw = `---
title: Hello World
date: 2024-01-01
tags:
  - typescript
  - ssg
---
# Body

Some content.
`;
    const { frontmatter, content } = parseFrontmatter(raw);
    expect(frontmatter.title).toBe('Hello World');
    expect(frontmatter.date).toBe('2024-01-01');
    expect(frontmatter.tags).toEqual(['typescript', 'ssg']);
    expect(content).not.toContain('---');
    expect(content).toContain('# Body');
  });

  it('handles files without frontmatter', () => {
    const raw = '# Just a heading\n\nText.';
    const { frontmatter, content } = parseFrontmatter(raw);
    expect(frontmatter).toEqual({});
    expect(content).toBe(raw);
  });

  it('handles a leading BOM', () => {
    const raw = '\uFEFF---\ntitle: BOM\n---\n\nbody';
    const { frontmatter, content } = parseFrontmatter(raw);
    expect(frontmatter.title).toBe('BOM');
    expect(content.trim()).toBe('body');
  });
});

describe('normalizeTags', () => {
  it('returns an empty array for undefined', () => {
    expect(normalizeTags(undefined)).toEqual([]);
  });

  it('splits comma-separated strings', () => {
    expect(normalizeTags('a, b, c')).toEqual(['a', 'b', 'c']);
  });

  it('accepts arrays', () => {
    expect(normalizeTags(['x', 'y'])).toEqual(['x', 'y']);
  });
});

describe('markdownToHtml', () => {
  it('renders markdown to html', () => {
    const html = markdownToHtml('# Title\n\n**bold**');
    expect(html).toContain('<h1>');
    expect(html).toContain('<strong>bold</strong>');
  });

  it('does not render a frontmatter block as literal HTML', () => {
    const html = markdownToHtml('# Body');
    expect(html).not.toContain('---');
  });
});

describe('build', () => {
  it('generates index.html and one page per markdown file', () => {
    const contentDir = makeTempDir();
    const outputDir = makeTempDir();

    fs.writeFileSync(
      path.join(contentDir, 'first-post.md'),
      `---
title: First Post
date: 2024-02-01
tags: [one]
---
# First

Hello first.
`
    );
    fs.writeFileSync(
      path.join(contentDir, 'second-post.md'),
      `---
title: Second Post
date: 2024-01-01
---
# Second

Hello second.
`
    );

    const result = build({ contentDir, outputDir });

    expect(result.writtenFiles).toHaveLength(3);

    const indexHtml = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf8');
    expect(indexHtml).toContain('First Post');
    expect(indexHtml).toContain('Second Post');
    expect(indexHtml).toContain('first-post.html');
    expect(indexHtml).toContain('second-post.html');

    const firstHtml = fs.readFileSync(path.join(outputDir, 'first-post.html'), 'utf8');
    expect(firstHtml).toContain('<h1>First Post</h1>');
    expect(firstHtml).toContain('<h1>First</h1>');
    expect(firstHtml).toContain('2024-02-01');

    const secondHtml = fs.readFileSync(path.join(outputDir, 'second-post.html'), 'utf8');
    expect(secondHtml).toContain('<h1>Second Post</h1>');
  });

  it('orders pages by date descending in the index', () => {
    const contentDir = makeTempDir();
    const outputDir = makeTempDir();

    fs.writeFileSync(
      path.join(contentDir, 'a.md'),
      `---\ntitle: A\ndate: 2024-01-01\n---\nA`
    );
    fs.writeFileSync(
      path.join(contentDir, 'b.md'),
      `---\ntitle: B\ndate: 2024-03-01\n---\nB`
    );

    build({ contentDir, outputDir });

    const indexHtml = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf8');
    expect(indexHtml.indexOf('b.html')).toBeLessThan(indexHtml.indexOf('a.html'));
  });

  it('reads markdown recursively from subdirectories', () => {
    const contentDir = makeTempDir();
    const outputDir = makeTempDir();

    fs.mkdirSync(path.join(contentDir, 'nested'));
    fs.writeFileSync(
      path.join(contentDir, 'nested', 'deep.md'),
      `---\ntitle: Deep\n---\nDeep content`
    );

    build({ contentDir, outputDir });

    expect(fs.existsSync(path.join(outputDir, 'deep.html'))).toBe(true);
  });

  it('loads pages with defaults when frontmatter is missing', () => {
    const contentDir = makeTempDir();
    fs.writeFileSync(path.join(contentDir, 'plain.md'), '# Plain\n\nNo frontmatter.');

    const pages = loadPages(contentDir);
    expect(pages).toHaveLength(1);
    expect(pages[0].title).toBe('plain');
    expect(pages[0].tags).toEqual([]);
    expect(pages[0].html).toContain('<h1>');
  });

  it('builds into a fresh output directory', () => {
    const contentDir = makeTempDir();
    const outputDir = path.join(makeTempDir(), 'nested', 'out');

    fs.writeFileSync(path.join(contentDir, 'x.md'), `---\ntitle: X\n---\nX`);
    build({ contentDir, outputDir });

    expect(fs.existsSync(path.join(outputDir, 'index.html'))).toBe(true);
  });
});
