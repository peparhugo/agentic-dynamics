import fs from 'fs';
import os from 'os';
import path from 'path';

import { main, parseArgs, USAGE } from '../cli';

function writeTree(root: string, files: Record<string, string>): void {
  for (const [rel, contents] of Object.entries(files)) {
    const full = path.join(root, rel);
    fs.mkdirSync(path.dirname(full), { recursive: true });
    fs.writeFileSync(full, contents);
  }
}

describe('parseArgs', () => {
  it('uses defaults for content, output and templates', () => {
    const options = parseArgs(['build']);
    expect(options.command).toBe('build');
    expect(options.contentDir).toBe(path.resolve('content'));
    expect(options.outputDir).toBe(path.resolve('dist'));
    expect(options.templatesDir).toBe(path.resolve('templates'));
    expect(options.help).toBe(false);
  });

  it('parses --content and --output', () => {
    const options = parseArgs(['build', '--content', 'src/md', '--output', 'public']);
    expect(options.command).toBe('build');
    expect(options.contentDir).toBe(path.resolve('src/md'));
    expect(options.outputDir).toBe(path.resolve('public'));
  });

  it('parses --templates', () => {
    const options = parseArgs(['build', '--templates', 'themes/site']);
    expect(options.templatesDir).toBe(path.resolve('themes/site'));
  });

  it('parses short flags -c and -o', () => {
    const options = parseArgs(['build', '-c', 'c', '-o', 'o']);
    expect(options.contentDir).toBe(path.resolve('c'));
    expect(options.outputDir).toBe(path.resolve('o'));
  });

  it('detects the help flag', () => {
    expect(parseArgs(['--help']).help).toBe(true);
    expect(parseArgs(['-h']).help).toBe(true);
  });

  it('does not require the command for flags', () => {
    const options = parseArgs(['--content', 'x', '--output', 'y', '--templates', 'z']);
    expect(options.contentDir).toBe(path.resolve('x'));
    expect(options.outputDir).toBe(path.resolve('y'));
    expect(options.templatesDir).toBe(path.resolve('z'));
  });
});

describe('main', () => {
  let contentDir: string;
  let outputDir: string;

  beforeEach(() => {
    contentDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-cli-content-'));
    outputDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-cli-dist-'));
  });

  afterEach(() => {
    fs.rmSync(contentDir, { recursive: true, force: true });
    fs.rmSync(outputDir, { recursive: true, force: true });
  });

  it('returns 0 and builds the site for the build command', () => {
    fs.writeFileSync(
      path.join(contentDir, 'post.md'),
      '---\ntitle: Post\n---\n# Post body'
    );

    const code = main([
      'node',
      'ssg',
      'build',
      '--content',
      contentDir,
      '--output',
      outputDir,
      '--templates',
      path.join(outputDir, 'missing-templates'),
    ]);

    expect(code).toBe(0);
    expect(fs.existsSync(path.join(outputDir, 'post.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'index.html'))).toBe(true);
  });

  it('renders pages through templates when a templates directory exists', () => {
    const templatesDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-cli-tpl-'));
    writeTree(templatesDir, {
      'default.hbs': '<article>{{title}}</article>',
      'layouts/default.hbs': '<html><body>{{{body}}}</body></html>',
    });
    fs.writeFileSync(
      path.join(contentDir, 'post.md'),
      '---\ntitle: Templated\n---\n# Post body'
    );

    const code = main([
      'node',
      'ssg',
      'build',
      '--content',
      contentDir,
      '--output',
      outputDir,
      '--templates',
      templatesDir,
    ]);

    expect(code).toBe(0);
    const html = fs.readFileSync(path.join(outputDir, 'post.html'), 'utf8');
    expect(html).toContain('<article>Templated</article>');
    expect(html).toContain('<html><body>');
    fs.rmSync(templatesDir, { recursive: true, force: true });
  });

  it('returns 1 for an unknown command', () => {
    const code = main(['node', 'ssg', 'serve']);
    expect(code).toBe(1);
  });

  it('returns 0 and prints usage for --help', () => {
    const spy = jest.spyOn(console, 'log').mockImplementation(() => {});
    const code = main(['node', 'ssg', '--help']);
    expect(code).toBe(0);
    expect(spy).toHaveBeenCalledWith(USAGE);
    spy.mockRestore();
  });
});
