import { parseArgs } from './cli';

describe('parseArgs', () => {
  it('defaults to build command with default paths', () => {
    const args = parseArgs([]);

    expect(args.command).toBe('build');
    expect(args.contentDir).toBe('./content');
    expect(args.outputDir).toBe('./dist');
  });

  it('parses build command', () => {
    const args = parseArgs(['build']);

    expect(args.command).toBe('build');
  });

  it('parses --content option', () => {
    const args = parseArgs(['--content', './my-content']);

    expect(args.contentDir).toBe('./my-content');
  });

  it('parses --output option', () => {
    const args = parseArgs(['--output', './my-dist']);

    expect(args.outputDir).toBe('./my-dist');
  });

  it('parses both --content and --output', () => {
    const args = parseArgs(['--content', './pages', '--output', './public']);

    expect(args.contentDir).toBe('./pages');
    expect(args.outputDir).toBe('./public');
  });

  it('parses command with options', () => {
    const args = parseArgs(['build', '--content', './content', '--output', './build']);

    expect(args.command).toBe('build');
    expect(args.contentDir).toBe('./content');
    expect(args.outputDir).toBe('./build');
  });

  it('handles options in different order', () => {
    const args = parseArgs(['--output', './out', 'build', '--content', './src']);

    expect(args.command).toBe('build');
    expect(args.contentDir).toBe('./src');
    expect(args.outputDir).toBe('./out');
  });

  it('ignores unknown options', () => {
    const args = parseArgs(['--unknown', 'value', '--content', './content']);

    expect(args.contentDir).toBe('./content');
  });

  it('handles missing value for option', () => {
    const args = parseArgs(['--content']);

    expect(args.contentDir).toBe('./content');
  });

  it('parses absolute paths', () => {
    const args = parseArgs(['--content', '/home/user/content', '--output', '/home/user/dist']);

    expect(args.contentDir).toBe('/home/user/content');
    expect(args.outputDir).toBe('/home/user/dist');
  });

  it('parses relative paths with multiple levels', () => {
    const args = parseArgs(['--content', '../../content', '--output', '../dist']);

    expect(args.contentDir).toBe('../../content');
    expect(args.outputDir).toBe('../dist');
  });
});
