import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { build } from '../src/builder';

function tmpdir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-test-'));
}

describe('build', () => {
  it('generates index.html and one HTML file per page', () => {
    const root = tmpdir();
    const content = path.join(root, 'content');
    const output = path.join(root, 'dist');
    fs.mkdirSync(content, { recursive: true });
    fs.writeFileSync(
      path.join(content, 'hello.md'),
      `---
title: Hello
date: 2024-02-01
tags: [greeting]
---
# Hello world
`
    );
    fs.writeFileSync(
      path.join(content, 'second.md'),
      `---
title: Second Post
---
Body two
`
    );

    const result = build({ contentDir: content, outputDir: output });

    expect(result.pages).toHaveLength(2);
    expect(fs.existsSync(path.join(output, 'index.html'))).toBe(true);
    expect(fs.existsSync(path.join(output, 'hello.html'))).toBe(true);
    expect(fs.existsSync(path.join(output, 'second.html'))).toBe(true);
  });

  it('lists all pages with links in index.html', () => {
    const root = tmpdir();
    const content = path.join(root, 'content');
    const output = path.join(root, 'dist');
    fs.mkdirSync(content, { recursive: true });
    fs.writeFileSync(
      path.join(content, 'alpha.md'),
      '---\ntitle: Alpha\n---\n# A\n'
    );
    fs.writeFileSync(
      path.join(content, 'beta.md'),
      '---\ntitle: Beta\n---\n# B\n'
    );

    build({ contentDir: content, outputDir: output });

    const index = fs.readFileSync(path.join(output, 'index.html'), 'utf8');
    expect(index).toContain('href="alpha.html"');
    expect(index).toContain('href="beta.html"');
    expect(index).toContain('Alpha');
    expect(index).toContain('Beta');
  });

  it('renders markdown body and frontmatter title into page HTML', () => {
    const root = tmpdir();
    const content = path.join(root, 'content');
    const output = path.join(root, 'dist');
    fs.mkdirSync(content, { recursive: true });
    fs.writeFileSync(
      path.join(content, 'post.md'),
      '---\ntitle: My Title\n---\n## Section\n\nHello *there*.\n'
    );

    build({ contentDir: content, outputDir: output });

    const page = fs.readFileSync(path.join(output, 'post.html'), 'utf8');
    expect(page).toContain('<title>My Title</title>');
    expect(page).toContain('<h1>My Title</h1>');
    expect(page).toContain('<h2>Section</h2>');
    expect(page).toContain('<em>there</em>');
    expect(page).not.toContain('---');
  });

  it('recurses into subdirectories and nests output paths', () => {
    const root = tmpdir();
    const content = path.join(root, 'content');
    const output = path.join(root, 'dist');
    const nested = path.join(content, 'blog', '2024');
    fs.mkdirSync(nested, { recursive: true });
    fs.writeFileSync(
      path.join(nested, 'post.md'),
      '---\ntitle: Nested\n---\n# Nested\n'
    );

    build({ contentDir: content, outputDir: output });

    expect(fs.existsSync(path.join(output, 'blog', '2024', 'post.html'))).toBe(
      true
    );
  });

  it('falls back to the slug as title when frontmatter has no title', () => {
    const root = tmpdir();
    const content = path.join(root, 'content');
    const output = path.join(root, 'dist');
    fs.mkdirSync(content, { recursive: true });
    fs.writeFileSync(path.join(content, 'untitled.md'), '# Heading only\n');

    const result = build({ contentDir: content, outputDir: output });

    expect(result.pages[0].title).toBe('untitled');
    const index = fs.readFileSync(path.join(output, 'index.html'), 'utf8');
    expect(index).toContain('untitled');
  });

  it('produces an empty index when no markdown files exist', () => {
    const root = tmpdir();
    const content = path.join(root, 'content');
    const output = path.join(root, 'dist');
    fs.mkdirSync(content, { recursive: true });

    const result = build({ contentDir: content, outputDir: output });

    expect(result.pages).toHaveLength(0);
    expect(fs.existsSync(path.join(output, 'index.html'))).toBe(true);
  });

  it('escapes HTML in titles and tag names', () => {
    const root = tmpdir();
    const content = path.join(root, 'content');
    const output = path.join(root, 'dist');
    fs.mkdirSync(content, { recursive: true });
    fs.writeFileSync(
      path.join(content, 'xss.md'),
      '---\ntitle: <script>alert(1)</script>\ntags: [<img>]\n---\nBody\n'
    );

    build({ contentDir: content, outputDir: output });

    const index = fs.readFileSync(path.join(output, 'index.html'), 'utf8');
    expect(index).toContain('&lt;script&gt;');
    expect(index).not.toContain('<script>alert(1)</script>');
  });
});
