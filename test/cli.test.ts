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
});
