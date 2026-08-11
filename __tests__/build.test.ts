import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import { build } from '../src/build';

function tmpDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-test-'));
}

function writeMarkdown(dir: string, slug: string, content: string, frontmatter: string = '') {
  const fm = frontmatter ? `${frontmatter}\n` : '';
  fs.writeFileSync(path.join(dir, `${slug}.md`), `---\n${fm}---\n${content}`);
}

describe('ssg build', () => {
  let contentDir: string;
  let outputDir: string;

  beforeEach(() => {
    contentDir = tmpDir();
    outputDir = tmpDir();
  });

  afterEach(() => {
    fs.rmSync(contentDir, { recursive: true, force: true });
    fs.rmSync(outputDir, { recursive: true, force: true });
  });

  it('throws when content directory does not exist', () => {
    expect(() => build('/nonexistent/dir', outputDir)).toThrow(/Content directory does not exist/);
  });

  it('creates output directory if it does not exist', () => {
    writeMarkdown(contentDir, 'hello', 'Hello world', 'title: Hello');
    const nestedOutput = path.join(outputDir, 'nested', 'out');
    build(contentDir, nestedOutput);
    expect(fs.existsSync(nestedOutput)).toBe(true);
    expect(fs.existsSync(path.join(nestedOutput, 'index.html'))).toBe(true);
  });

  it('generates an index.html listing all pages', () => {
    writeMarkdown(contentDir, 'alpha', 'Content A', 'title: Alpha');
    writeMarkdown(contentDir, 'beta', 'Content B', 'title: Beta');

    build(contentDir, outputDir);

    const indexHtml = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf-8');
    expect(indexHtml).toContain('href="alpha.html"');
    expect(indexHtml).toContain('href="beta.html"');
    expect(indexHtml).toContain('Alpha');
    expect(indexHtml).toContain('Beta');
  });

  it('generates an HTML file for each markdown page', () => {
    writeMarkdown(contentDir, 'welcome', '# Welcome\n\nSome content', 'title: Welcome');
    writeMarkdown(contentDir, 'about', '## About\n\nAbout text', 'title: About');

    build(contentDir, outputDir);

    expect(fs.existsSync(path.join(outputDir, 'welcome.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'about.html'))).toBe(true);
  });

  it('parses markdown to HTML', () => {
    writeMarkdown(contentDir, 'test', '# Heading\n\n**bold** text', 'title: Test');

    build(contentDir, outputDir);

    const html = fs.readFileSync(path.join(outputDir, 'test.html'), 'utf-8');
    expect(html).toContain('<h1>Heading</h1>');
    expect(html).toContain('<strong>bold</strong>');
  });

  it('uses frontmatter title in the HTML page', () => {
    writeMarkdown(contentDir, 'mypage', 'Content', 'title: My Custom Title');

    build(contentDir, outputDir);

    const html = fs.readFileSync(path.join(outputDir, 'mypage.html'), 'utf-8');
    expect(html).toContain('<title>My Custom Title</title>');
    expect(html).toContain('<h1>My Custom Title</h1>');
  });

  it('displays date from frontmatter', () => {
    writeMarkdown(contentDir, 'post', 'Body', 'title: Post\ndate: 2024-06-15');

    build(contentDir, outputDir);

    const html = fs.readFileSync(path.join(outputDir, 'post.html'), 'utf-8');
    expect(html).toContain('2024-06-15');
  });

  it('displays tags from frontmatter', () => {
    writeMarkdown(contentDir, 'tagged', 'Content', 'title: Tagged\ntags:\n  - javascript\n  - typescript');

    build(contentDir, outputDir);

    const html = fs.readFileSync(path.join(outputDir, 'tagged.html'), 'utf-8');
    expect(html).toContain('javascript');
    expect(html).toContain('typescript');
  });

  it('escapes HTML in metadata', () => {
    writeMarkdown(contentDir, 'xss', 'Body', 'title: <script>alert("xss")</script>');

    build(contentDir, outputDir);

    const html = fs.readFileSync(path.join(outputDir, 'xss.html'), 'utf-8');
    expect(html).not.toContain('<script>alert("xss")</script>');
    expect(html).toContain('&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;');
  });

  it('sorts pages by date descending on the index page', () => {
    writeMarkdown(contentDir, 'old', 'Old', 'title: Old\ndate: 2023-01-01');
    writeMarkdown(contentDir, 'new', 'New', 'title: New\ndate: 2024-12-31');

    build(contentDir, outputDir);

    const indexHtml = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf-8');
    const newPos = indexHtml.indexOf('href="new.html"');
    const oldPos = indexHtml.indexOf('href="old.html"');
    expect(newPos).toBeLessThan(oldPos);
  });

  it('handles empty content directory gracefully', () => {
    build(contentDir, outputDir);

    const indexHtml = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf-8');
    expect(indexHtml).toContain('No pages found');
  });

  it('uses slug as fallback title when no frontmatter title', () => {
    writeMarkdown(contentDir, 'fallback', 'Content');

    build(contentDir, outputDir);

    const html = fs.readFileSync(path.join(outputDir, 'fallback.html'), 'utf-8');
    expect(html).toContain('<title>fallback</title>');
  });

  it('produces a link back to index on each page', () => {
    writeMarkdown(contentDir, 'linked', 'Body', 'title: Linked');

    build(contentDir, outputDir);

    const html = fs.readFileSync(path.join(outputDir, 'linked.html'), 'utf-8');
    expect(html).toContain('href="index.html"');
    expect(html).toContain('Home');
  });

  it('renders code blocks from markdown', () => {
    writeMarkdown(contentDir, 'code', '```\nconst x = 1;\n```', 'title: Code');

    build(contentDir, outputDir);

    const html = fs.readFileSync(path.join(outputDir, 'code.html'), 'utf-8');
    expect(html).toContain('<code>');
  });

  it('handles pages without tags gracefully', () => {
    writeMarkdown(contentDir, 'notags', 'Body', 'title: No Tags');

    build(contentDir, outputDir);

    const html = fs.readFileSync(path.join(outputDir, 'notags.html'), 'utf-8');
    expect(html).toContain('<title>No Tags</title>');
    expect(html).not.toMatch(/<span class="tag">/);
  });
});
