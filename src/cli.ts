#!/usr/bin/env node
import { buildSite, buildSiteIncremental } from './build';
import { Page } from './page';
import { DEFAULT_PORT, ServeOptions, startDevServer } from './serve';

export interface BuildOptions {
  content: string;
  output: string;
  templates: string;
  incremental?: boolean;
  clean?: boolean;
}

export type CliOptions = BuildOptions | ServeOptions;

export interface ParsedCli {
  command: 'build' | 'serve';
  options: CliOptions;
}

const DEFAULT_CONTENT = './content';
const DEFAULT_OUTPUT = './dist';
const DEFAULT_TEMPLATES = './templates';

function usage(): string {
  return [
    'Usage: ssg <command> [options]',
    '',
    'Commands:',
    '  build   Build the static site',
    '  serve   Start the development server with live reload',
    '',
    'Options:',
    '  --content <dir>    Markdown source directory (default: ./content)',
    '  --output <dir>     Output directory (default: ./dist)',
    '  --templates <dir>  Template directory (default: ./templates)',
    '  --port <number>    Port for the dev server (default: 3000)',
    '  --incremental      Rebuild only changed pages (uses .ssg-cache.json)',
    '  --clean            Force a clean rebuild, ignoring the cache',
    '  -h, --help         Show this help',
  ].join('\n');
}

function parseFlagValue(argv: string[], flag: string, index: number): string | null {
  const arg = argv[index];
  if (arg === flag) {
    const value = argv[index + 1];
    return value !== undefined ? value : null;
  }
  if (arg.startsWith(`${flag}=`)) {
    return arg.slice(flag.length + 1);
  }
  return null;
}

export function parseArgs(argv: string[]): ParsedCli | null {
  const args = argv.slice();
  const command = args.shift();
  if (command === undefined || command === '-h' || command === '--help') return null;
  if (command !== 'build' && command !== 'serve') return null;

  const options: BuildOptions = { content: DEFAULT_CONTENT, output: DEFAULT_OUTPUT, templates: DEFAULT_TEMPLATES };
  let port = DEFAULT_PORT;

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === '-h' || arg === '--help') return null;
    const contentValue = parseFlagValue(args, '--content', i);
    if (contentValue !== null) {
      options.content = contentValue;
      if (args[i] === '--content') i++;
      continue;
    }
    const outputValue = parseFlagValue(args, '--output', i);
    if (outputValue !== null) {
      options.output = outputValue;
      if (args[i] === '--output') i++;
      continue;
    }
    const templatesValue = parseFlagValue(args, '--templates', i);
    if (templatesValue !== null) {
      options.templates = templatesValue;
      if (args[i] === '--templates') i++;
      continue;
    }
    if (command === 'serve') {
      const portValue = parseFlagValue(args, '--port', i);
      if (portValue !== null) {
        const parsedPort = Number(portValue);
        if (Number.isInteger(parsedPort) && parsedPort > 0 && parsedPort <= 65535) {
          port = parsedPort;
        } else {
          return null;
        }
        if (args[i] === '--port') i++;
        continue;
      }
    }
    if (command === 'build') {
      if (arg === '--incremental') {
        options.incremental = true;
        continue;
      }
      if (arg === '--clean') {
        options.clean = true;
        continue;
      }
    }
    return null;
  }

  if (command === 'serve') {
    return { command, options: { ...options, port } };
  }
  return { command, options };
}

export function run(argv: string[]): number {
  const parsed = parseArgs(argv);
  if (parsed === null) {
    process.stdout.write(usage() + '\n');
    return 1;
  }

  try {
    if (parsed.command === 'serve') {
      const options = parsed.options as ServeOptions;
      const devServer = startDevServer(options);
      process.stdout.write(`Serving ${options.output} at ${devServer.address()}\n`);
      process.stdout.write(`Watching ${options.content} and ${options.templates} for changes...\n`);
      return 0;
    }
    const options = parsed.options as BuildOptions;
    if (options.incremental === true || options.clean === true) {
      const result = buildSiteIncremental(options.content, options.output, options.templates, {
        clean: options.clean === true,
      });
      process.stdout.write(
        `Built ${result.stats.pagesBuilt} page(s), skipped ${result.stats.pagesSkipped}, saved ${result.stats.timeSavedMs}ms\n`
      );
      return 0;
    }
    const pages: Page[] = buildSite(options.content, options.output, options.templates);
    process.stdout.write(`Built ${pages.length} page(s) into ${options.output}\n`);
    return 0;
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    process.stderr.write(`Error: ${message}\n`);
    return 1;
  }
}

function main(): void {
  process.exitCode = run(process.argv.slice(2));
}

if (require.main === module) {
  main();
}
