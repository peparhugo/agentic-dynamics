import { describe, it, expect } from 'vitest';
import { parseArgs } from '../src/cli';

describe('parseArgs', () => {
  it('parses build command with all required options', () => {
    const opts = parseArgs([
      'node',
      'static-gen',
      'build',
      '-s',
      './content',
      '-t',
      './templates',
      '-o',
      './dist',
    ]);

    expect(opts.command).toBe('build');
    expect(opts.source).toBe('./content');
    expect(opts.templates).toBe('./templates');
    expect(opts.output).toBe('./dist');
  });

  it('parses build command with --drafts flag', () => {
    const opts = parseArgs([
      'node',
      'static-gen',
      'build',
      '-s',
      './content',
      '-t',
      './templates',
      '-o',
      './dist',
      '--drafts',
    ]);

    expect(opts.drafts).toBe(true);
  });

  it('parses build command with -d short flag', () => {
    const opts = parseArgs([
      'node',
      'static-gen',
      'build',
      '-s',
      './content',
      '-t',
      './templates',
      '-o',
      './dist',
      '-d',
    ]);

    expect(opts.drafts).toBe(true);
  });

  it('parses serve command with required options', () => {
    const opts = parseArgs([
      'node',
      'static-gen',
      'serve',
      '-s',
      './content',
      '-t',
      './templates',
      '-o',
      './dist',
    ]);

    expect(opts.command).toBe('serve');
    expect(opts.source).toBe('./content');
    expect(opts.templates).toBe('./templates');
    expect(opts.output).toBe('./dist');
  });

  it('parses serve command with custom port', () => {
    const opts = parseArgs([
      'node',
      'static-gen',
      'serve',
      '-s',
      './content',
      '-t',
      './templates',
      '-o',
      './dist',
      '-p',
      '8080',
    ]);

    expect(opts.port).toBe(8080);
  });

  it('parses serve command with --port flag', () => {
    const opts = parseArgs([
      'node',
      'static-gen',
      'serve',
      '-s',
      './content',
      '-t',
      './templates',
      '-o',
      './dist',
      '--port',
      '9090',
    ]);

    expect(opts.port).toBe(9090);
  });

  it('defaults port to 3000 when not specified', () => {
    const opts = parseArgs([
      'node',
      'static-gen',
      'serve',
      '-s',
      './content',
      '-t',
      './templates',
      '-o',
      './dist',
    ]);

    expect(opts.port).toBe(3000);
  });

  it('defaults drafts to false', () => {
    const opts = parseArgs([
      'node',
      'static-gen',
      'build',
      '-s',
      './content',
      '-t',
      './templates',
      '-o',
      './dist',
    ]);

    expect(opts.drafts).toBe(false);
  });

  it('defaults command to build when not specified', () => {
    const opts = parseArgs([
      'node',
      'static-gen',
      '-s',
      './content',
      '-t',
      './templates',
      '-o',
      './dist',
    ]);

    // commander treats the first non-option as the command
    expect(opts.command).toBe('build');
  });
});
