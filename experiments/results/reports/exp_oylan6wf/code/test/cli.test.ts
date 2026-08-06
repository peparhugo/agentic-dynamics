import { describe, expect, it } from 'vitest';
import { parseArgs, CliError, HELP } from '../src/cli.js';

describe('parseArgs', () => {
  it('defaults to help with no args', () => {
    expect(parseArgs([]).command).toBe('help');
  });

  it('parses the build command with default config', () => {
    const opts = parseArgs(['build']);
    expect(opts.command).toBe('build');
    expect(opts.config.sourceDir).toBe('content');
    expect(opts.config.templateDir).toBe('templates');
    expect(opts.config.outDir).toBe('dist-site');
    expect(opts.config.includeDrafts).toBe(false);
    expect(opts.port).toBe(3000);
  });

  it('parses long flags with separate values', () => {
    const opts = parseArgs([
      'build',
      '--source', 'src-md',
      '--templates', 'tpl',
      '--out', 'public',
      '--base-url', 'https://x.dev',
      '--title', 'X',
      '--description', 'desc',
    ]);
    expect(opts.config).toMatchObject({
      sourceDir: 'src-md',
      templateDir: 'tpl',
      outDir: 'public',
      baseUrl: 'https://x.dev',
      title: 'X',
      description: 'desc',
    });
  });

  it('parses --flag=value syntax', () => {
    const opts = parseArgs(['serve', '--port=8080', '--source=c']);
    expect(opts.command).toBe('serve');
    expect(opts.port).toBe(8080);
    expect(opts.config.sourceDir).toBe('c');
  });

  it('parses short aliases', () => {
    const opts = parseArgs(['build', '-s', 'a', '-t', 'b', '-o', 'c', '-d']);
    expect(opts.config.sourceDir).toBe('a');
    expect(opts.config.templateDir).toBe('b');
    expect(opts.config.outDir).toBe('c');
    expect(opts.config.includeDrafts).toBe(true);
  });

  it('flag order is independent of the command position', () => {
    const opts = parseArgs(['--drafts', 'build', '--port', '4000']);
    expect(opts.command).toBe('build');
    expect(opts.config.includeDrafts).toBe(true);
    expect(opts.port).toBe(4000);
  });

  it('-h/--help wins as command', () => {
    expect(parseArgs(['-h']).command).toBe('help');
    expect(parseArgs(['build', '--help']).command).toBe('help');
  });

  it('rejects unknown commands and flags', () => {
    expect(() => parseArgs(['deploy'])).toThrow(CliError);
    expect(() => parseArgs(['build', '--frobnicate'])).toThrow(/Unknown flag/);
    expect(() => parseArgs(['build', 'extra'])).toThrow(/Unexpected argument/);
  });

  it('rejects missing and invalid values', () => {
    expect(() => parseArgs(['build', '--source'])).toThrow(/requires a value/);
    expect(() => parseArgs(['serve', '--port', 'abc'])).toThrow(/Invalid port/);
    expect(() => parseArgs(['serve', '--port', '0'])).toThrow(/Invalid port/);
    expect(() => parseArgs(['serve', '--port', '70000'])).toThrow(/Invalid port/);
  });

  it('HELP text documents both commands', () => {
    expect(HELP).toContain('sprout build');
    expect(HELP).toContain('sprout serve');
  });
});
