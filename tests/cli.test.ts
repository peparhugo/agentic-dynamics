import { parseArgs } from '../src/cli';

describe('parseArgs', () => {
  it('returns defaults when no command is provided', () => {
    const options = parseArgs([]);
    expect(options.command).toBe('');
    expect(options.content).toBe('./content');
    expect(options.output).toBe('./dist');
    expect(options.templates).toBe('./templates');
  });

  it('parses the build command with content and output options', () => {
    const options = parseArgs([
      'build',
      '--content',
      'docs',
      '--output',
      'site',
    ]);
    expect(options.command).toBe('build');
    expect(options.content).toBe('docs');
    expect(options.output).toBe('site');
  });

  it('supports --flag=value syntax', () => {
    const options = parseArgs(['build', '--content=posts', '--output=public']);
    expect(options.command).toBe('build');
    expect(options.content).toBe('posts');
    expect(options.output).toBe('public');
  });

  it('supports short -c and -o aliases', () => {
    const options = parseArgs(['build', '-c', 'src', '-o', 'out']);
    expect(options.command).toBe('build');
    expect(options.content).toBe('src');
    expect(options.output).toBe('out');
  });

  it('parses options regardless of order', () => {
    const options = parseArgs(['--output', 'x', 'build', '--content', 'y']);
    expect(options.command).toBe('build');
    expect(options.content).toBe('y');
    expect(options.output).toBe('x');
  });

  it('parses the help flag', () => {
    expect(parseArgs(['--help']).command).toBe('help');
    expect(parseArgs(['-h']).command).toBe('help');
  });

  it('parses the templates option', () => {
    const options = parseArgs([
      'build',
      '--content',
      'docs',
      '--output',
      'site',
      '--templates',
      'theme',
    ]);
    expect(options.templates).toBe('theme');

    expect(parseArgs(['build', '--templates=theme']).templates).toBe('theme');
    expect(parseArgs(['build', '-t', 'theme']).templates).toBe('theme');
  });
});
