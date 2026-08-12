import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { execFile } from 'node:child_process';
import { parseArgs } from '../src/cli';

function makeTempDir(): string {
  return mkdtempSync(path.join(tmpdir(), 'ssg-cli-test-'));
}

describe('parseArgs', () => {
  it('uses defaults when no options are given', () => {
    const parsed = parseArgs([]);
    expect(parsed.ok).toBe(true);
    if (parsed.ok) {
      expect(parsed.options.contentDir).toBe(path.resolve('content'));
      expect(parsed.options.outputDir).toBe(path.resolve('dist'));
    }
  });

  it('parses --content and --output', () => {
    const parsed = parseArgs(['--content', 'src/pages', '--output', 'public']);
    expect(parsed.ok).toBe(true);
    if (parsed.ok) {
      expect(parsed.options.contentDir).toBe(path.resolve('src/pages'));
      expect(parsed.options.outputDir).toBe(path.resolve('public'));
      expect(parsed.options.templatesDir).toBe(path.resolve('templates'));
    }
  });

  it('parses --templates', () => {
    const parsed = parseArgs(['--templates', 'theme', '--templates=other']);
    expect(parsed.ok).toBe(true);
    if (parsed.ok) {
      expect(parsed.options.templatesDir).toBe(path.resolve('other'));
    }
  });

  it('parses --content=value style flags', () => {
    const parsed = parseArgs(['--content=in', '--output=out']);
    expect(parsed.ok).toBe(true);
    if (parsed.ok) {
      expect(parsed.options.contentDir).toBe(path.resolve('in'));
      expect(parsed.options.outputDir).toBe(path.resolve('out'));
    }
  });

  it('rejects unknown flags', () => {
    const parsed = parseArgs(['--bogus']);
    expect(parsed.ok).toBe(false);
  });
});

function runCli(cwd: string, args: string[]): Promise<{ stdout: string; stderr: string; code: number | null }> {
  const cli = path.resolve(__dirname, '..', 'dist', 'cli.js');
  return new Promise((resolve, reject) => {
    execFile(process.execPath, [cli, ...args], { cwd }, (error, stdout, stderr) => {
      if (error && error.code === undefined) {
        reject(error);
        return;
      }
      resolve({ stdout, stderr, code: error ? (error.code as number | null) : 0 });
    });
  });
}

describe('ssg build (end to end)', () => {
  it('builds the site with the default content and output directories', async () => {
    const dir = makeTempDir();
    mkdirSync(path.join(dir, 'content'));
    writeFileSync(
      path.join(dir, 'content', 'hello.md'),
      '---\ntitle: Hello\ndate: 2024-05-01\n---\n# Hello World\n',
      'utf8',
    );

    const { stdout, code } = await runCli(dir, ['build']);

    expect(code).toBe(0);
    expect(stdout).toContain('Generated 1 page(s)');
    expect(existsSync(path.join(dir, 'dist', 'index.html'))).toBe(true);
    expect(existsSync(path.join(dir, 'dist', 'hello.html'))).toBe(true);
    expect(readFileSync(path.join(dir, 'dist', 'hello.html'), 'utf8')).toContain('<h1>Hello World</h1>');
  });

  it('respects --content and --output options', async () => {
    const dir = makeTempDir();
    mkdirSync(path.join(dir, 'pages'));
    writeFileSync(path.join(dir, 'pages', 'post.md'), '---\ntitle: Post\n---\nBody text\n', 'utf8');

    const { code } = await runCli(dir, ['build', '--content', 'pages', '--output', 'site']);

    expect(code).toBe(0);
    expect(existsSync(path.join(dir, 'site', 'index.html'))).toBe(true);
    expect(existsSync(path.join(dir, 'site', 'post.html'))).toBe(true);
    expect(existsSync(path.join(dir, 'dist'))).toBe(false);
  });

  it('fails with a non-zero exit code for an unknown command', async () => {
    const dir = makeTempDir();
    const { code, stderr } = await runCli(dir, ['serve']);
    expect(code).toBe(1);
    expect(stderr).toContain('Usage');
  });

  it('renders pages with templates, layouts, and partials via --templates', async () => {
    const dir = makeTempDir();
    mkdirSync(path.join(dir, 'content'));
    writeFileSync(path.join(dir, 'content', 'hello.md'), '---\ntitle: Hello\ndate: 2024-05-01\n---\n# Hello World\n', 'utf8');
    mkdirSync(path.join(dir, 'templates'), { recursive: true });
    writeFileSync(path.join(dir, 'templates', 'default.hbs'), '{{> header}}<h1>{{title}}</h1>{{{body}}}{{> footer}}', 'utf8');
    mkdirSync(path.join(dir, 'templates', 'layouts'), { recursive: true });
    writeFileSync(path.join(dir, 'templates', 'layouts', 'default.hbs'), '<html><body>{{{body}}}</body></html>', 'utf8');
    mkdirSync(path.join(dir, 'templates', 'partials'), { recursive: true });
    writeFileSync(path.join(dir, 'templates', 'partials', 'header.hbs'), '<header>Header</header>', 'utf8');
    writeFileSync(path.join(dir, 'templates', 'partials', 'footer.hbs'), '<footer>Footer</footer>', 'utf8');

    const { stdout, code } = await runCli(dir, ['build', '--templates', 'templates']);

    expect(code).toBe(0);
    expect(stdout).toContain('Generated 1 page(s)');

    const html = readFileSync(path.join(dir, 'dist', 'hello.html'), 'utf8');
    expect(html).toContain('<html><body><header>Header</header>');
    expect(html).toContain('<h1>Hello</h1>');
    expect(html).toContain('<h1>Hello World</h1>');
    expect(html).toContain('<footer>Footer</footer>');
  });
});
