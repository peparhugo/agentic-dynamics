import { parseArgs } from '../src/cli';

describe('parseArgs', () => {
  it('defaults to the build command with ./content and ./dist', () => {
    expect(parseArgs(['node', 'ssg', 'build'])).toEqual({
      command: 'build',
      contentDir: './content',
      outputDir: './dist',
      templatesDir: './templates',
      port: 3000,
      incremental: false,
      clean: false,
    });
  });

  it('parses --content and --output as separate arguments', () => {
    const opts = parseArgs(['node', 'ssg', 'build', '--content', 'posts', '--output', 'site']);
    expect(opts).toEqual({ command: 'build', contentDir: 'posts', outputDir: 'site', templatesDir: './templates', port: 3000, incremental: false, clean: false });
  });

  it('parses --content= and --output= syntax', () => {
    const opts = parseArgs(['node', 'ssg', 'build', '--content=posts', '--output=site']);
    expect(opts).toEqual({ command: 'build', contentDir: 'posts', outputDir: 'site', templatesDir: './templates', port: 3000, incremental: false, clean: false });
  });

  it('parses --templates and --templates= syntax', () => {
    expect(parseArgs(['node', 'ssg', 'build', '--templates', 'layouts'])).toEqual({
      command: 'build',
      contentDir: './content',
      outputDir: './dist',
      templatesDir: 'layouts',
      port: 3000,
      incremental: false,
      clean: false,
    });
    expect(parseArgs(['node', 'ssg', 'build', '--templates=layouts'])).toEqual({
      command: 'build',
      contentDir: './content',
      outputDir: './dist',
      templatesDir: 'layouts',
      port: 3000,
      incremental: false,
      clean: false,
    });
  });

  it('treats a positional as the command', () => {
    expect(parseArgs(['node', 'ssg', 'serve']).command).toBe('serve');
  });

  it('keeps the default when a flag value is missing', () => {
    const opts = parseArgs(['node', 'ssg', 'build', '--content']);
    expect(opts.contentDir).toBe('./content');
  });

  it('parses --port as a separate argument', () => {
    const opts = parseArgs(['node', 'ssg', 'serve', '--port', '8080']);
    expect(opts.port).toBe(8080);
    expect(opts.command).toBe('serve');
  });

  it('parses --port= syntax', () => {
    const opts = parseArgs(['node', 'ssg', 'serve', '--port=9090']);
    expect(opts.port).toBe(9090);
  });

  it('defaults the port to 3000 for the serve command', () => {
    expect(parseArgs(['node', 'ssg', 'serve']).port).toBe(3000);
  });

  it('parses the --incremental flag', () => {
    expect(parseArgs(['node', 'ssg', 'build', '--incremental']).incremental).toBe(true);
  });

  it('parses the --clean flag', () => {
    expect(parseArgs(['node', 'ssg', 'build', '--incremental', '--clean'])).toEqual({
      command: 'build',
      contentDir: './content',
      outputDir: './dist',
      templatesDir: './templates',
      port: 3000,
      incremental: true,
      clean: true,
    });
  });
});
