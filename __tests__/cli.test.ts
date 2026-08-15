import { parseArgs, HelpError } from '../src/cli';

describe('parseArgs', () => {
  it('defaults to build with ./content and ./dist', () => {
    const { command, options } = parseArgs([]);
    expect(command).toBe('build');
    expect(options.contentDir).toBe('content');
    expect(options.outputDir).toBe('dist');
    expect(options.templatesDir).toBe('templates');
  });

  it('parses --content and --output', () => {
    const { command, options } = parseArgs([
      'build',
      '--content',
      'pages',
      '--output',
      'public',
    ]);
    expect(command).toBe('build');
    expect(options.contentDir).toBe('pages');
    expect(options.outputDir).toBe('public');
  });

  it('parses --templates', () => {
    const { options } = parseArgs(['build', '--templates', 'theme']);
    expect(options.templatesDir).toBe('theme');
  });

  it('supports = syntax', () => {
    const { options } = parseArgs(['build', '--content=posts', '--output=site', '--templates=theme']);
    expect(options.contentDir).toBe('posts');
    expect(options.outputDir).toBe('site');
    expect(options.templatesDir).toBe('theme');
  });

  it('parses --incremental and --clean flags', () => {
    const { options } = parseArgs(['build', '--incremental', '--clean']);
    expect(options.incremental).toBe(true);
    expect(options.clean).toBe(true);
  });

  it('does not enable incremental by default', () => {
    const { options } = parseArgs(['build']);
    expect(options.incremental).toBeUndefined();
    expect(options.clean).toBeUndefined();
  });

  it('throws for unknown arguments', () => {
    expect(() => parseArgs(['build', '--bogus'])).toThrow('unknown argument');
  });

  it('throws for an unknown command', () => {
    expect(() => parseArgs(['deploy'])).toThrow('unknown command');
  });

  it('throws HelpError for --help', () => {
    expect(() => parseArgs(['--help'])).toThrow(HelpError);
  });

  it('parses the serve command with defaults', () => {
    const { command, options, port } = parseArgs(['serve']);
    expect(command).toBe('serve');
    expect(options.contentDir).toBe('content');
    expect(options.outputDir).toBe('dist');
    expect(options.templatesDir).toBe('templates');
    expect(port).toBeUndefined();
  });

  it('parses --port for the serve command', () => {
    const { command, port } = parseArgs(['serve', '--port', '8080']);
    expect(command).toBe('serve');
    expect(port).toBe(8080);
  });

  it('supports --port with = syntax', () => {
    const { port } = parseArgs(['serve', '--port=9090']);
    expect(port).toBe(9090);
  });

  it('rejects an invalid --port value', () => {
    expect(() => parseArgs(['serve', '--port', 'abc'])).toThrow(
      '--port must be an integer'
    );
  });

  it('combines serve with content, output, templates, and port', () => {
    const { command, options, port } = parseArgs([
      'serve',
      '--content',
      'pages',
      '--output',
      'public',
      '--templates',
      'theme',
      '--port',
      '4000',
    ]);
    expect(command).toBe('serve');
    expect(options.contentDir).toBe('pages');
    expect(options.outputDir).toBe('public');
    expect(options.templatesDir).toBe('theme');
    expect(port).toBe(4000);
  });
});
