import { parseArgs } from '../src/cli';

describe('parseArgs', () => {
  it('parses the build command with defaults', () => {
    expect(parseArgs(['node', 'cli.js', 'build'])).toEqual({ command: 'build' });
  });

  it('parses --content and --output options', () => {
    expect(parseArgs(['node', 'cli.js', 'build', '--content', 'src/pages', '--output', 'public'])).toEqual({
      command: 'build',
      content: 'src/pages',
      output: 'public',
    });
  });

  it('parses --content= and --output= options', () => {
    expect(parseArgs(['node', 'cli.js', 'build', '--content=content', '--output=dist'])).toEqual({
      command: 'build',
      content: 'content',
      output: 'dist',
    });
  });

  it('parses short flags', () => {
    expect(parseArgs(['node', 'cli.js', 'build', '-c', 'c', '-o', 'o'])).toEqual({
      command: 'build',
      content: 'c',
      output: 'o',
    });
  });

  it('parses --templates option', () => {
    expect(parseArgs(['node', 'cli.js', 'build', '--templates', 'tpl'])).toEqual({
      command: 'build',
      templates: 'tpl',
    });
  });

  it('parses --templates= option', () => {
    expect(parseArgs(['node', 'cli.js', 'build', '--templates=tpl'])).toEqual({
      command: 'build',
      templates: 'tpl',
    });
  });

  it('parses the serve command with defaults', () => {
    expect(parseArgs(['node', 'cli.js', 'serve'])).toEqual({ command: 'serve' });
  });

  it('parses --port for the serve command', () => {
    expect(parseArgs(['node', 'cli.js', 'serve', '--port', '8080'])).toEqual({
      command: 'serve',
      port: 8080,
    });
  });

  it('parses --port= for the serve command', () => {
    expect(parseArgs(['node', 'cli.js', 'serve', '--port=8080'])).toEqual({
      command: 'serve',
      port: 8080,
    });
  });

  it('parses a short -p port flag', () => {
    expect(parseArgs(['node', 'cli.js', 'serve', '-p', '9000'])).toEqual({
      command: 'serve',
      port: 9000,
    });
  });
});
