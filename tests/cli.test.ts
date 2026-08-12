import { execSync } from 'child_process';
import { existsSync, readFileSync } from 'fs';
import { join } from 'path';
import { parseArgs, run } from '../src/cli';
import { createFixture, cleanupFixture, Fixture } from './helpers';

describe('parseArgs', () => {
  it('uses defaults for content and output', () => {
    const parsed = parseArgs(['build']);
    expect(parsed).toEqual({
      command: 'build',
      options: { content: './content', output: './dist', templates: './templates' },
    });
  });

  it('accepts --content and --output flags', () => {
    const parsed = parseArgs(['build', '--content', 'src/md', '--output', 'public']);
    expect(parsed).toEqual({
      command: 'build',
      options: { content: 'src/md', output: 'public', templates: './templates' },
    });
  });

  it('accepts --content=dir syntax', () => {
    const parsed = parseArgs(['build', '--content=posts', '--output=out']);
    expect(parsed).toEqual({
      command: 'build',
      options: { content: 'posts', output: 'out', templates: './templates' },
    });
  });

  it('accepts a --templates flag', () => {
    const parsed = parseArgs(['build', '--templates', 'themes/site']);
    expect(parsed).toEqual({
      command: 'build',
      options: { content: './content', output: './dist', templates: 'themes/site' },
    });
  });

  it('rejects unknown subcommands', () => {
    expect(parseArgs(['publish'])).toBeNull();
  });

  it('rejects unknown flags', () => {
    expect(parseArgs(['build', '--bogus'])).toBeNull();
  });
});

describe('run', () => {
  let fixture: Fixture;

  afterEach(() => {
    cleanupFixture(fixture);
  });

  it('builds the site and returns exit code 0', () => {
    fixture = createFixture({
      'hello.md': '---\ntitle: Hello\n---\n\nHi there.',
    });

    const code = run(['build', '--content', fixture.contentDir, '--output', fixture.outputDir]);
    expect(code).toBe(0);
    expect(existsSync(join(fixture.outputDir, 'hello.html'))).toBe(true);
    expect(existsSync(join(fixture.outputDir, 'index.html'))).toBe(true);
  });

  it('returns exit code 1 and reports an error for a missing content dir', () => {
    fixture = createFixture({});

    const code = run(['build', '--content', join(fixture.root, 'missing'), '--output', fixture.outputDir]);
    expect(code).toBe(1);
  });

  it('returns exit code 1 for invalid arguments', () => {
    fixture = createFixture({});
    expect(run(['publish'])).toBe(1);
  });
});

describe('compiled CLI binary', () => {
  let fixture: Fixture;

  beforeAll(() => {
    execSync('npx tsc -p tsconfig.json', { cwd: process.cwd(), stdio: 'pipe' });
  });

  afterEach(() => {
    cleanupFixture(fixture);
  });

  it('supports `ssg build` end to end', () => {
    fixture = createFixture({
      'post.md': '---\ntitle: Post\ndate: 2024-01-01\n---\n\nBody.',
    });

    const cli = join(process.cwd(), 'dist', 'cli.js');
    const output = execSync(`node ${cli} build --content ${fixture.contentDir} --output ${fixture.outputDir}`, {
      encoding: 'utf8',
    });

    expect(output).toContain('Built 1 page(s)');
    expect(existsSync(join(fixture.outputDir, 'post.html'))).toBe(true);
    const page = readFileSync(join(fixture.outputDir, 'post.html'), 'utf8');
    expect(page).toContain('<title>Post</title>');
  });

  it('fails with a non-zero exit when the content dir is missing', () => {
    fixture = createFixture({});

    let failed = false;
    try {
      execSync(
        `node ${join(process.cwd(), 'dist', 'cli.js')} build --content ${join(fixture.root, 'nope')} --output ${fixture.outputDir}`,
        { stdio: 'pipe' }
      );
    } catch (err) {
      failed = (err as { status?: number }).status !== 0;
    }
    expect(failed).toBe(true);
  });
});
