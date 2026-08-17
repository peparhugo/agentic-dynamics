import { parseArgs } from '../src/cli';

describe('parseArgs', () => {
  it('parses the build command with default directories', () => {
    const options = parseArgs(['build']);
    expect(options.command).toBe('build');
    expect(options.content).toBe('./content');
    expect(options.output).toBe('./dist');
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
});
