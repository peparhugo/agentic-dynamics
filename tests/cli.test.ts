import { parseArgs } from '../src/cli';

describe('parseArgs', () => {
  it('defaults to the build command with ./content and ./dist', () => {
    expect(parseArgs(['node', 'ssg', 'build'])).toEqual({
      command: 'build',
      contentDir: './content',
      outputDir: './dist',
      templatesDir: './templates',
    });
  });

  it('parses --content and --output as separate arguments', () => {
    const opts = parseArgs(['node', 'ssg', 'build', '--content', 'posts', '--output', 'site']);
    expect(opts).toEqual({ command: 'build', contentDir: 'posts', outputDir: 'site', templatesDir: './templates' });
  });

  it('parses --content= and --output= syntax', () => {
    const opts = parseArgs(['node', 'ssg', 'build', '--content=posts', '--output=site']);
    expect(opts).toEqual({ command: 'build', contentDir: 'posts', outputDir: 'site', templatesDir: './templates' });
  });

  it('parses --templates and --templates= syntax', () => {
    expect(parseArgs(['node', 'ssg', 'build', '--templates', 'layouts'])).toEqual({
      command: 'build',
      contentDir: './content',
      outputDir: './dist',
      templatesDir: 'layouts',
    });
    expect(parseArgs(['node', 'ssg', 'build', '--templates=layouts'])).toEqual({
      command: 'build',
      contentDir: './content',
      outputDir: './dist',
      templatesDir: 'layouts',
    });
  });

  it('treats a positional as the command', () => {
    expect(parseArgs(['node', 'ssg', 'serve']).command).toBe('serve');
  });

  it('keeps the default when a flag value is missing', () => {
    const opts = parseArgs(['node', 'ssg', 'build', '--content']);
    expect(opts.contentDir).toBe('./content');
  });
});
