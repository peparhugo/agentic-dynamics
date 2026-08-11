import fs from 'fs';
import path from 'path';
import os from 'os';
import { build } from '../src/ssg';

const testContentDir = path.join(__dirname, 'content');
const testOutputDir = path.join(__dirname, 'output');

function setupOutputDir() {
  if (fs.existsSync(testOutputDir)) {
    fs.rmSync(testOutputDir, { recursive: true });
  }
  fs.mkdirSync(testOutputDir, { recursive: true });
}

describe('SSG build', () => {
  beforeEach(() => {
    setupOutputDir();
  });

  afterEach(() => {
    if (fs.existsSync(testOutputDir)) {
      fs.rmSync(testOutputDir, { recursive: true });
    }
  });

  test('generates index.html', () => {
    build({ contentDir: testContentDir, outputDir: testOutputDir });

    const indexPath = path.join(testOutputDir, 'index.html');
    expect(fs.existsSync(indexPath)).toBe(true);

    const indexContent = fs.readFileSync(indexPath, 'utf-8');
    expect(indexContent).toContain('Hello World');
    expect(indexContent).toContain('Getting Started');
    expect(indexContent).toContain('hello-world.html');
    expect(indexContent).toContain('getting-started.html');
    expect(indexContent).toContain('1/15/2024');
    expect(indexContent).toContain('2/20/2024');
    expect(indexContent).toContain('intro, typescript');
    expect(indexContent).toContain('guide');
  });

  test('generates individual page HTML files', () => {
    build({ contentDir: testContentDir, outputDir: testOutputDir });

    const helloPath = path.join(testOutputDir, 'hello-world.html');
    expect(fs.existsSync(helloPath)).toBe(true);

    const helloContent = fs.readFileSync(helloPath, 'utf-8');
    expect(helloContent).toContain('<title>Hello World</title>');
    expect(helloContent).toContain('<h1>Hello World</h1>');
    expect(helloContent).toContain('This is a test page.');
    expect(helloContent).toContain('<a href="index.html">Back to index</a>');

    const gsPath = path.join(testOutputDir, 'getting-started.html');
    expect(fs.existsSync(gsPath)).toBe(true);

    const gsContent = fs.readFileSync(gsPath, 'utf-8');
    expect(gsContent).toContain('<title>Getting Started</title>');
    expect(gsContent).toContain('<h1>Getting Started</h1>');
    expect(gsContent).toContain('<strong>bold</strong>');
    expect(gsContent).toContain('<em>italic</em>');
    expect(gsContent).toContain('<code>npm install</code>');
  });

  test('handles empty content directory', () => {
    const emptyDir = path.join(os.tmpdir(), 'ssg-empty-' + Date.now());
    fs.mkdirSync(emptyDir, { recursive: true });

    try {
      build({ contentDir: emptyDir, outputDir: testOutputDir });

      const indexPath = path.join(testOutputDir, 'index.html');
      expect(fs.existsSync(indexPath)).toBe(true);

      const indexContent = fs.readFileSync(indexPath, 'utf-8');
      expect(indexContent).toContain('<h1>Pages</h1>');
      expect(indexContent).not.toContain('<li>');
    } finally {
      fs.rmSync(emptyDir, { recursive: true });
    }
  });

  test('handles non-existent content directory', () => {
    build({ contentDir: '/tmp/nonexistent-dir-ssg-test', outputDir: testOutputDir });

    const indexPath = path.join(testOutputDir, 'index.html');
    expect(fs.existsSync(indexPath)).toBe(true);

    const indexContent = fs.readFileSync(indexPath, 'utf-8');
    expect(indexContent).toContain('<h1>Pages</h1>');
    expect(indexContent).not.toContain('<li>');
  });

  test('creates output directory if it does not exist', () => {
    const newOutput = path.join(os.tmpdir(), 'ssg-new-output-' + Date.now());
    expect(fs.existsSync(newOutput)).toBe(false);

    try {
      build({ contentDir: testContentDir, outputDir: newOutput });
      expect(fs.existsSync(newOutput)).toBe(true);
      expect(fs.existsSync(path.join(newOutput, 'index.html'))).toBe(true);
    } finally {
      fs.rmSync(newOutput, { recursive: true });
    }
  });

  test('index page lists all pages sorted', () => {
    build({ contentDir: testContentDir, outputDir: testOutputDir });

    const indexContent = fs.readFileSync(path.join(testOutputDir, 'index.html'), 'utf-8');

    const helloIndex = indexContent.indexOf('Hello World');
    const gsIndex = indexContent.indexOf('Getting Started');
    // Both should appear; order depends on file read order
    expect(helloIndex).toBeGreaterThan(-1);
    expect(gsIndex).toBeGreaterThan(-1);
  });

  test('page without frontmatter uses slug as title', () => {
    const dir = path.join(os.tmpdir(), 'ssg-nofm-' + Date.now());
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(path.join(dir, 'no-title.md'), '# Just content\n\nNo frontmatter here.');

    try {
      build({ contentDir: dir, outputDir: testOutputDir });

      const pagePath = path.join(testOutputDir, 'no-title.html');
      expect(fs.existsSync(pagePath)).toBe(true);
      const content = fs.readFileSync(pagePath, 'utf-8');
      expect(content).toContain('<title>no-title</title>');
    } finally {
      fs.rmSync(dir, { recursive: true });
    }
  });
});
