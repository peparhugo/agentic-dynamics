import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { parseArgs, run } from './cli';

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
});
