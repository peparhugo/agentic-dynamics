#!/usr/bin/env node
import { buildSite } from './site';
import { startDevServer } from './server';

function usage(): string {
  return 'Usage: ssg <build|serve> [--content <dir>] [--output <dir>] [--templates <dir>] [--port <port>]';
}

interface CliOptions {
  contentDir?: string;
  outputDir?: string;
  templateDir?: string;
  port?: number;
}

function parseArguments(args: string[]): CliOptions {
  const options: CliOptions = {};
  for (let index = 0; index < args.length; index += 1) {
    const argument = args[index];
    if (argument === '--content' || argument === '--output' || argument === '--templates' || argument === '--port') {
      const value = args[index + 1];
      if (!value) throw new Error(`Missing value for ${argument}`);
      if (argument === '--content') options.contentDir = value;
      else if (argument === '--output') options.outputDir = value;
      else if (argument === '--templates') options.templateDir = value;
      else {
        const port = Number(value);
        if (!Number.isInteger(port) || port < 0 || port > 65535) throw new Error(`Invalid port: ${value}`);
        options.port = port;
      }
      index += 1;
    } else {
      throw new Error(`Unknown option: ${argument}`);
    }
  }
  return options;
}

async function main(): Promise<void> {
  const [command, ...args] = process.argv.slice(2);
  if (command !== 'build' && command !== 'serve') throw new Error(usage());
  const options = parseArguments(args);
  if (command === 'build') {
    const pages = await buildSite(options);
    process.stdout.write(`Built ${pages.length} page(s).\n`);
    return;
  }

  const devServer = await startDevServer(options);
  process.stdout.write(`Serving on http://localhost:${devServer.port}\n`);
  const close = (): void => { void devServer.close(); };
  process.once('SIGINT', close);
  process.once('SIGTERM', close);
}

main().catch((error: unknown) => {
  process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
  process.exitCode = 1;
});
