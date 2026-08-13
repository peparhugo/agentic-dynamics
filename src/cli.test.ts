import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { parseArgs, run } from './cli';
import { ServeHandle } from './serve';

describe('parseArgs', () => {
  it('defaults to the build command with default directories', () => {
    expect(parseArgs(['build'])).toEqual({
      command: 'build',
      contentDir: './content',
      outputDir: './dist',
    });
  });

  it('parses --content and --output overrides', () => {
    expect(parseArgs(['build', '--content', './src-content', '--output', './public'])).toEqual({
      command: 'build',
      contentDir: './src-content',
      outputDir: './public',
    });
  });

  it('throws when --content is missing its value', () => {
    expect(() => parseArgs(['build', '--content'])).toThrow(/--content requires/);
  });

  it('throws on an unknown flag', () => {
    expect(() => parseArgs(['build', '--bogus'])).toThrow(/Unknown argument/);
  });

  it('parses a --templates override', () => {
    expect(parseArgs(['build', '--templates', './my-templates'])).toEqual({
      command: 'build',
      contentDir: './content',
      outputDir: './dist',
      templatesDir: './my-templates',
    });
  });

  it('throws when --templates is missing its value', () => {
    expect(() => parseArgs(['build', '--templates'])).toThrow(/--templates requires/);
  });

  it('parses a --port override for the serve command', () => {
    expect(parseArgs(['serve', '--port', '4000'])).toEqual({
      command: 'serve',
      contentDir: './content',
      outputDir: './dist',
      port: 4000,
    });
  });

  it('throws when --port is missing its value', () => {
    expect(() => parseArgs(['serve', '--port'])).toThrow(/--port requires/);
  });

  it('throws when --port is not a number', () => {
    expect(() => parseArgs(['serve', '--port', 'abc'])).toThrow(/--port requires/);
  });
});

describe('run', () => {
  let contentDir: string;
  let outputDir: string;

  beforeEach(() => {
    contentDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-cli-content-'));
    outputDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-cli-output-'));
    fs.writeFileSync(path.join(contentDir, 'page.md'), '---\ntitle: Page\n---\nHello');
  });

  afterEach(() => {
    fs.rmSync(contentDir, { recursive: true, force: true });
    fs.rmSync(outputDir, { recursive: true, force: true });
  });

  it('builds the site end-to-end via the CLI entrypoint', () => {
    run(['build', '--content', contentDir, '--output', outputDir]);
    expect(fs.existsSync(path.join(outputDir, 'index.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'page.html'))).toBe(true);
  });

  it('rejects an unknown command', () => {
    expect(() => run(['deploy'])).toThrow(/Unknown command/);
  });

  it('starts a live-reload dev server via the serve command', async () => {
    const handle = run(['serve', '--content', contentDir, '--output', outputDir, '--port', '0']) as ServeHandle;
    try {
      expect(handle.port).toBeGreaterThan(0);
      expect(fs.existsSync(path.join(outputDir, 'index.html'))).toBe(true);
    } finally {
      await handle.close();
    }
  });
});
