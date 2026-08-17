#!/usr/bin/env node
import { buildSite } from './generate';
import { serveSite } from './server';

export interface CliOptions {
  command: string | null;
  content: string;
  output: string;
  templates: string;
  port: number;
  help: boolean;
  incremental: boolean;
  clean: boolean;
}

export function parseArgs(args: string[]): CliOptions {
  const options: CliOptions = {
    command: null,
    content: './content',
    output: './dist',
    templates: './templates',
    port: 3000,
    help: false,
    incremental: false,
    clean: false,
  };

  for (let i = 0; i < args.length; i += 1) {
    const arg = args[i];
    if (arg === 'build' || arg === 'serve') {
      options.command = arg;
    } else if (arg === '--content' || arg === '-c') {
      options.content = args[i + 1] ?? options.content;
      if (args[i + 1] !== undefined) i += 1;
    } else if (arg.startsWith('--content=')) {
      options.content = arg.slice('--content='.length);
    } else if (arg === '--output' || arg === '-o') {
      options.output = args[i + 1] ?? options.output;
      if (args[i + 1] !== undefined) i += 1;
    } else if (arg.startsWith('--output=')) {
      options.output = arg.slice('--output='.length);
    } else if (arg === '--templates' || arg === '-t') {
      options.templates = args[i + 1] ?? options.templates;
      if (args[i + 1] !== undefined) i += 1;
    } else if (arg.startsWith('--templates=')) {
      options.templates = arg.slice('--templates='.length);
    } else if (arg === '--port' || arg === '-p') {
      const value = args[i + 1];
      if (value !== undefined) {
        const parsed = Number.parseInt(value, 10);
        if (!Number.isNaN(parsed)) options.port = parsed;
        i += 1;
      }
    } else if (arg.startsWith('--port=')) {
      const parsed = Number.parseInt(arg.slice('--port='.length), 10);
      if (!Number.isNaN(parsed)) options.port = parsed;
    } else if (arg === '--incremental') {
      options.incremental = true;
    } else if (arg === '--clean') {
      options.clean = true;
    } else if (arg === '--help' || arg === '-h') {
      options.help = true;
    }
  }

  return options;
}

export function printUsage(): string {
  return [
    'Usage: npx ssg <command> [options]',
    '',
    'Commands:',
    '  build   Build a static site from Markdown files.',
    '  serve   Start a development server with live reload.',
    '',
    'Options:',
    '  --content <dir>, -c <dir>  Markdown content directory (default: ./content)',
    '  --output <dir>,  -o <dir>  Output directory (default: ./dist)',
    '  --templates <dir>, -t <dir> Template directory (default: ./templates)',
    '  --port <port>,   -p <port> Port for the dev server (default: 3000)',
    '  --incremental               Rebuild only pages whose source or template changed.',
    '  --clean                     Force a full rebuild (ignore the cache manifest).',
    '  --help, -h                 Show this help message',
  ].join('\n');
}

export async function run(argv: string[]): Promise<void> {
  const options = parseArgs(argv.slice(2));

  if (options.help || (options.command !== 'build' && options.command !== 'serve')) {
    process.stdout.write(`${printUsage()}\n`);
    return;
  }

  if (options.command === 'serve') {
    const devServer = await serveSite({
      content: options.content,
      output: options.output,
      templates: options.templates,
      port: options.port,
    });
    process.stdout.write(`Serving ${options.output} at http://localhost:${devServer.port}\n`);
    return;
  }

  const result = await buildSite(options.content, options.output, options.templates, {
    incremental: options.incremental,
    clean: options.clean,
  });
  if (options.incremental) {
    process.stdout.write(
      `Built ${result.stats.pagesBuilt} page(s), skipped ${result.stats.pagesSkipped} page(s) into ${options.output}\n`
    );
  } else {
    process.stdout.write(`Built ${result.pages.length} page(s) into ${options.output}\n`);
  }
}

if (require.main === module) {
  run(process.argv).catch((err: unknown) => {
    const message = err instanceof Error ? err.message : String(err);
    process.stderr.write(`${message}\n`);
    process.exitCode = 1;
  });
}
