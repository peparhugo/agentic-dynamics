#!/usr/bin/env node

import * as path from 'path';
import { buildSite, DEFAULT_CONTENT_DIR, DEFAULT_OUTPUT_DIR, DEFAULT_TEMPLATES_DIR, DEFAULT_SITE_TITLE } from './build';
import { startDevServer, DEFAULT_PORT } from './dev-server';

export interface CliOptions {
  command?: 'build' | 'serve';
  contentDir: string;
  outputDir: string;
  siteTitle: string;
  templatesDir: string;
  defaultTemplate?: string;
  defaultLayout?: string;
  port?: number;
  help?: boolean;
}

export function parseCliArgs(argv: string[]): CliOptions {
  const args = argv.slice(2);
  const options: CliOptions = {
    contentDir: DEFAULT_CONTENT_DIR,
    outputDir: DEFAULT_OUTPUT_DIR,
    siteTitle: DEFAULT_SITE_TITLE,
    templatesDir: DEFAULT_TEMPLATES_DIR,
  };

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === '--content') {
      options.contentDir = args[++i] ?? DEFAULT_CONTENT_DIR;
    } else if (arg.startsWith('--content=')) {
      options.contentDir = arg.slice('--content='.length) || DEFAULT_CONTENT_DIR;
    } else if (arg === '--output') {
      options.outputDir = args[++i] ?? DEFAULT_OUTPUT_DIR;
    } else if (arg.startsWith('--output=')) {
      options.outputDir = arg.slice('--output='.length) || DEFAULT_OUTPUT_DIR;
    } else if (arg === '--templates') {
      options.templatesDir = args[++i] ?? DEFAULT_TEMPLATES_DIR;
    } else if (arg.startsWith('--templates=')) {
      options.templatesDir = arg.slice('--templates='.length) || DEFAULT_TEMPLATES_DIR;
    } else if (arg === '--template') {
      options.defaultTemplate = args[++i];
    } else if (arg.startsWith('--template=')) {
      options.defaultTemplate = arg.slice('--template='.length);
    } else if (arg === '--layout') {
      options.defaultLayout = args[++i];
    } else if (arg.startsWith('--layout=')) {
      options.defaultLayout = arg.slice('--layout='.length);
    } else if (arg === '--title') {
      options.siteTitle = args[++i] ?? DEFAULT_SITE_TITLE;
    } else if (arg.startsWith('--title=')) {
      options.siteTitle = arg.slice('--title='.length) || DEFAULT_SITE_TITLE;
    } else if (arg === 'build') {
      options.command = 'build';
    } else if (arg === 'serve') {
      options.command = 'serve';
    } else if (arg === '--port') {
      options.port = parsePort(args[++i]);
    } else if (arg.startsWith('--port=')) {
      options.port = parsePort(arg.slice('--port='.length));
    } else if (arg === '--help' || arg === '-h') {
      options.help = true;
    } else {
      throw new Error(`Unknown argument: ${arg}`);
    }
  }

  return options;
}

function parsePort(value: string | undefined): number | undefined {
  if (value === undefined) {
    throw new Error('--port requires a value');
  }
  const port = Number(value);
  if (!Number.isInteger(port) || port < 0 || port > 65535) {
    throw new Error(`Invalid port: ${value}`);
  }
  return port;
}

function printUsage(): void {
  console.log('ssg build [options]');
  console.log('');
  console.log('Build a static site from Markdown files.');
  console.log('');
  console.log('Options:');
  console.log('  --content <dir>     Markdown content directory (default: ./content)');
  console.log('  --output <dir>      Output directory for generated HTML (default: ./dist)');
  console.log('  --templates <dir>   Template directory (default: ./templates)');
  console.log('  --template <name>   Default page template to use when none is set');
  console.log('  --layout <name>     Default layout to use when none is set');
  console.log('  --title <text>      Site title used in the generated pages');
  console.log('  -h, --help          Show this help');
  console.log('');
  console.log('ssg serve [options]');
  console.log('');
  console.log('Start a live-reload dev server for the site.');
  console.log('');
  console.log('Options:');
  console.log('  --port <number>     Port for the dev server (default: 3000)');
  console.log('  --content <dir>     Markdown content directory (default: ./content)');
  console.log('  --output <dir>      Output directory for generated HTML (default: ./dist)');
  console.log('  --templates <dir>   Template directory (default: ./templates)');
  console.log('  --template <name>   Default page template to use when none is set');
  console.log('  --layout <name>     Default layout to use when none is set');
  console.log('  --title <text>      Site title used in the generated pages');
  console.log('  -h, --help          Show this help');
}

async function runServe(options: CliOptions): Promise<number> {
  const instance = await startDevServer({
    contentDir: options.contentDir,
    outputDir: options.outputDir,
    templatesDir: options.templatesDir,
    siteTitle: options.siteTitle,
    defaultTemplate: options.defaultTemplate,
    defaultLayout: options.defaultLayout,
    port: options.port ?? DEFAULT_PORT,
  });
  console.log(`Dev server running at http://localhost:${instance.port}`);
  console.log(`Watching ${path.resolve(options.contentDir)} and ${path.resolve(options.templatesDir)}`);
  console.log('Press Ctrl+C to stop.');

  const shutdown = async (): Promise<void> => {
    await instance.close();
  };
  process.once('SIGINT', () => {
    shutdown().then(() => process.exit(0));
  });
  process.once('SIGTERM', () => {
    shutdown().then(() => process.exit(0));
  });

  return await new Promise<number>((resolve) => {
    instance.server.on('close', () => resolve(0));
  });
}

export async function run(argv: string[]): Promise<number> {
  let options: CliOptions;
  try {
    options = parseCliArgs(argv);
  } catch (error) {
    console.error(`Error: ${(error as Error).message}`);
    printUsage();
    return 1;
  }

  if (options.help) {
    printUsage();
    return 0;
  }

  try {
    if (options.command === 'serve') {
      return await runServe(options);
    }

    const pages = await buildSite(options);
    const content = path.resolve(options.contentDir);
    const output = path.resolve(options.outputDir);
    console.log(`Generated ${pages.length} page(s) from ${content} into ${output}`);
    return 0;
  } catch (error) {
    const message = (error as Error).message;
    if (options.command === 'serve') {
      console.error(`Dev server failed: ${message}`);
    } else {
      console.error(`Build failed: ${message}`);
    }
    return 1;
  }
}

export function main(): void {
  run(process.argv).then((code) => {
    process.exitCode = code;
  });
}

if (require.main === module) {
  main();
}
