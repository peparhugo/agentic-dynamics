#!/usr/bin/env node

import { build, DEFAULT_CONTENT_DIR, DEFAULT_OUTPUT_DIR, DEFAULT_TEMPLATES_DIR } from './ssg';
import { DEFAULT_PORT, ServeOptions, startServe } from './serve';

export interface CliOptions {
  command: string;
  content: string;
  output: string;
  templates: string;
  port: number;
}

/**
 * Parse CLI arguments for the `ssg` binary.
 * Usage: ssg build [--content <dir>] [--output <dir>] [--templates <dir>]
 *        ssg serve [--content <dir>] [--output <dir>] [--templates <dir>] [--port <port>]
 */
export function parseArgs(argv: string[]): CliOptions {
  if (argv.includes('--help') || argv.includes('-h')) {
    throw new HelpError();
  }

  const options: CliOptions = {
    command: argv[0] ?? '',
    content: DEFAULT_CONTENT_DIR,
    output: DEFAULT_OUTPUT_DIR,
    templates: DEFAULT_TEMPLATES_DIR,
    port: DEFAULT_PORT,
  };

  const flags = argv.slice(1);
  for (let i = 0; i < flags.length; i++) {
    const flag = flags[i];
    if (flag === '--content' || flag === '--output' || flag === '--templates' || flag === '--port') {
      const value = flags[i + 1];
      if (value === undefined) {
        throw new Error(`Missing value for ${flag}`);
      }
      if (flag === '--content') {
        options.content = value;
      } else if (flag === '--output') {
        options.output = value;
      } else if (flag === '--templates') {
        options.templates = value;
      } else {
        const parsedPort = Number(value);
        if (!Number.isInteger(parsedPort) || parsedPort < 0 || parsedPort > 65535) {
          throw new Error(`Invalid port: ${value}`);
        }
        options.port = parsedPort;
      }
      i++;
    } else {
      throw new Error(`Unknown option: ${flag}`);
    }
  }

  return options;
}

export class HelpError extends Error {
  constructor() {
    super('help requested');
    this.name = 'HelpError';
  }
}

export const USAGE = `Usage: ssg build [--content <dir>] [--output <dir>] [--templates <dir>]
       ssg serve [--content <dir>] [--output <dir>] [--templates <dir>] [--port <port>]

Build a static site from Markdown files, or run a live-reload dev server.

Commands:
  build                   Generate the static site once
  serve                   Start a dev server with live reload

Options:
  --content <dir>     Directory containing Markdown sources (default: ${DEFAULT_CONTENT_DIR})
  --output <dir>      Directory where the generated site is written (default: ${DEFAULT_OUTPUT_DIR})
  --templates <dir>   Directory containing templates, layouts, and partials (default: ${DEFAULT_TEMPLATES_DIR})
  --port <port>       Port for the dev server (default: ${DEFAULT_PORT})
  -h, --help          Show this help message
`;

/** Build serve options from parsed CLI options. */
export function toServeOptions(options: CliOptions): ServeOptions {
  return {
    content: options.content,
    output: options.output,
    templates: options.templates,
    port: options.port,
  };
}

/**
 * Run the CLI with a given argument list and return a human-readable summary.
 * Exported separately from `main` so it can be exercised in tests.
 */
export function run(argv: string[]): string {
  let options: CliOptions;
  try {
    options = parseArgs(argv);
  } catch (err) {
    if (err instanceof HelpError) {
      return USAGE;
    }
    throw err;
  }

  if (options.command !== 'build') {
    throw new Error(`Unknown command: ${options.command}\n\n${USAGE}`);
  }

  const pages = build(options.content, options.output, options.templates);
  return `Built ${pages.length} page(s) into ${options.output}`;
}

function serveCommand(args: string[]): void {
  let options: CliOptions;
  try {
    options = parseArgs(['serve', ...args]);
  } catch (err) {
    process.stderr.write((err instanceof Error ? err.message : String(err)) + '\n');
    process.exitCode = 1;
    return;
  }
  startServe(toServeOptions(options)).catch((err) => {
    process.stderr.write((err instanceof Error ? err.message : String(err)) + '\n');
    process.exitCode = 1;
  });
}

function main(): void {
  const argv = process.argv.slice(2);
  if (argv[0] === 'serve') {
    serveCommand(argv.slice(1));
    return;
  }
  try {
    const message = run(argv);
    process.stdout.write(message + '\n');
  } catch (err) {
    process.stderr.write(
      (err instanceof Error ? err.message : String(err)) + '\n'
    );
    process.exitCode = 1;
  }
}

if (require.main === module) {
  main();
}
