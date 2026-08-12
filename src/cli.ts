#!/usr/bin/env node
import { build, BuildOptions } from './ssg';
import { startDevServer, DEFAULT_SERVE_PORT } from './serve';

const DEFAULT_COMMAND = 'build';

interface CliOptions extends BuildOptions {
  port?: number;
}

function printUsage(): void {
  console.log(`Usage:
  ssg build [options]
  ssg serve [options]

Commands:
  build   Generate the static site into the output directory
  serve   Run a live-reload development server

Options:
  --content <dir>     Source directory for Markdown files (default: ./content)
  --output <dir>      Output directory for generated HTML (default: ./dist)
  --templates <dir>   Directory for Handlebars templates (default: ./templates)
  --port <number>     Port for the dev server (default: ${DEFAULT_SERVE_PORT})
  --help              Show this help`);
}

function parseArgs(argv: string[]): { command: string; options: CliOptions; help: boolean } {
  const options: CliOptions = {};
  let help = false;
  let command = DEFAULT_COMMAND;

  let idx = 0;
  while (idx < argv.length) {
    const arg = argv[idx];
    switch (arg) {
      case '--help':
      case '-h':
        help = true;
        idx += 1;
        break;
      case '--content':
        options.contentDir = argv[idx + 1];
        idx += 2;
        break;
      case '--output':
        options.outputDir = argv[idx + 1];
        idx += 2;
        break;
      case '--templates':
        options.templateDir = argv[idx + 1];
        idx += 2;
        break;
      case '--port':
        options.port = Number.parseInt(argv[idx + 1], 10);
        idx += 2;
        break;
      default:
        if (arg.startsWith('-')) {
          idx += 1;
        } else {
          command = arg;
          idx += 1;
        }
    }
  }

  return { command, options, help };
}

function main(): void {
  const { command, options, help } = parseArgs(process.argv.slice(2));

  if (help) {
    printUsage();
    return;
  }

  if (command === 'build') {
    const pages = build(options);
    console.log(`Generated ${pages.length} page(s) into ${options.outputDir ?? './dist'}`);
    return;
  }

  if (command === 'serve') {
    const dev = startDevServer(options);
    const port = options.port ?? DEFAULT_SERVE_PORT;
    console.log(`[ssg] Dev server running at http://localhost:${port}`);
    console.log(`[ssg] Serving ./dist; watching content/ and templates/ for changes`);
    process.on('SIGINT', () => {
      dev.close().then(() => process.exit(0));
    });
    return;
  }

  printUsage();
  process.exitCode = 1;
}

if (require.main === module) {
  main();
}

export { parseArgs, main };
