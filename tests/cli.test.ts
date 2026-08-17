import { parseArgs } from '../src/cli';

describe('parseArgs', () => {
  it('parses the build command with default directories', () => {
    const options = parseArgs(['build']);
    expect(options.command).toBe('build');
    expect(options.content).toBe('./content');
    expect(options.output).toBe('./dist');
    expect(options.templates).toBe('./templates');
    expect(options.help).toBe(false);
  });

  it('parses --content and --output flags', () => {
    const options = parseArgs(['build', '--content', 'posts', '--output', 'site']);
    expect(options.content).toBe('posts');
    expect(options.output).toBe('site');
  });

  it('parses short flags', () => {
    const options = parseArgs(['build', '-c', 'posts', '-o', 'site']);
    expect(options.content).toBe('posts');
    expect(options.output).toBe('site');
  });

  it('parses --flag=value form', () => {
    const options = parseArgs(['build', '--content=posts', '--output=public']);
    expect(options.content).toBe('posts');
    expect(options.output).toBe('public');
  });

  it('sets help flag', () => {
    const options = parseArgs(['--help']);
    expect(options.help).toBe(true);
    expect(options.command).toBeNull();
  });

  it('leaves command null when no build subcommand is present', () => {
    const options = parseArgs(['--content', 'posts']);
    expect(options.command).toBeNull();
    expect(options.content).toBe('posts');
  });

  it('parses --templates and -t flags', () => {
    expect(parseArgs(['build', '--templates', 'views']).templates).toBe('views');
    expect(parseArgs(['build', '-t', 'views']).templates).toBe('views');
    expect(parseArgs(['build', '--templates=views']).templates).toBe('views');
  });

  it('parses the serve command', () => {
    const options = parseArgs(['serve']);
    expect(options.command).toBe('serve');
    expect(options.port).toBe(3000);
  });

  it('parses the --port flag for the serve command', () => {
    expect(parseArgs(['serve', '--port', '8080']).port).toBe(8080);
    expect(parseArgs(['serve', '-p', '8080']).port).toBe(8080);
    expect(parseArgs(['serve', '--port=8080']).port).toBe(8080);
  });

  it('ignores an invalid --port value and keeps the default', () => {
    expect(parseArgs(['serve', '--port', 'not-a-number']).port).toBe(3000);
  });

  it('parses the --incremental and --clean flags', () => {
    expect(parseArgs(['build', '--incremental']).incremental).toBe(true);
    expect(parseArgs(['build', '--clean']).clean).toBe(true);
    expect(parseArgs(['build']).incremental).toBe(false);
    expect(parseArgs(['build']).clean).toBe(false);
  });
});
