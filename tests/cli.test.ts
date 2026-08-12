import fs from 'fs';
import os from 'os';
import path from 'path';
import { parseArgs, run, USAGE, HelpError } from '../src/cli';
import { DEFAULT_CONTENT_DIR, DEFAULT_OUTPUT_DIR } from '../src/ssg';

describe('parseArgs', () => {
  it('uses the default directories when no options are given', () => {
    const options = parseArgs(['build']);
    expect(options.command).toBe('build');
    expect(options.content).toBe(DEFAULT_CONTENT_DIR);
    expect(options.output).toBe(DEFAULT_OUTPUT_DIR);
  });

  it('parses --content and --output options', () => {
    const options = parseArgs(['build', '--content', 'pages', '--output', 'public']);
    expect(options.command).toBe('build');
    expect(options.content).toBe('pages');
    expect(options.output).toBe('public');
  });

  it('throws when a flag is missing its value', () => {
    expect(() => parseArgs(['build', '--content'])).toThrow(/Missing value/);
  });

  it('throws on unknown options', () => {
    expect(() => parseArgs(['build', '--bogus'])).toThrow(/Unknown option/);
  });

  it('throws HelpError for --help', () => {
    expect(() => parseArgs(['build', '--help'])).toThrow(HelpError);
  });
});

describe('run', () => {
  it('builds a site and reports how many pages were generated', () => {
    const content = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-content-'));
    const output = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-out-'));
    try {
      fs.writeFileSync(path.join(content, 'one.md'), '<!--\ntitle: One\n-->\n# One');
      fs.writeFileSync(path.join(content, 'two.md'), '<!--\ntitle: Two\n-->\n# Two');

      const message = run(['build', '--content', content, '--output', output]);

      expect(message).toContain('Built 2 page(s)');
      expect(fs.existsSync(path.join(output, 'one.html'))).toBe(true);
      expect(fs.existsSync(path.join(output, 'two.html'))).toBe(true);
      expect(fs.existsSync(path.join(output, 'index.html'))).toBe(true);
    } finally {
      fs.rmSync(content, { recursive: true, force: true });
      fs.rmSync(output, { recursive: true, force: true });
    }
  });

  it('throws for an unknown command', () => {
    expect(() => run(['serve'])).toThrow(/Unknown command/);
  });

  it('returns the usage text for --help', () => {
    expect(run(['--help'])).toContain('Usage: ssg build');
    expect(USAGE).toContain('--content <dir>');
    expect(USAGE).toContain('--output <dir>');
  });

  it('surfaces a missing content directory as an error', () => {
    expect(() => run(['build', '--content', 'no-such-dir-xyz'])).toThrow(
      /Content directory not found/
    );
  });
});
