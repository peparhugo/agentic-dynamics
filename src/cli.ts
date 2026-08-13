#!/usr/bin/env node
import { buildSite } from './generator';
import { startDevServer } from './server';

function usage(): string {
  return 'Usage: ssg <build|serve> [--content <dir>] [--output <dir>] [--port <number>]';
}

function parseArguments(arguments_: string[], allowPort = false): { contentDir?: string; outputDir?: string; port?: number } {
  const options: { contentDir?: string; outputDir?: string; port?: number } = {};
  for (let index = 0; index < arguments_.length; index += 1) {
    const argument = arguments_[index];
    if (argument === '--content' || argument === '--output' || (allowPort && argument === '--port')) {
      const value = arguments_[index + 1];
      if (!value || value.startsWith('--')) throw new Error(`Missing value for ${argument}`);
      if (argument === '--port') {
        const port = Number(value);
        if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('Port must be an integer between 1 and 65535');
        options.port = port;
      } else {
        options[argument === '--content' ? 'contentDir' : 'outputDir'] = value;
      }
      index += 1;
    } else {
      throw new Error(`Unknown option: ${argument}`);
    }
  }
  return options;
}

async function main(): Promise<void> {
  const [command, ...arguments_] = process.argv.slice(2);
  if (command !== 'build' && command !== 'serve') throw new Error(usage());
  const options = parseArguments(arguments_, command === 'serve');
  if (command === 'serve') {
    await startDevServer(options);
    return;
  }
  const pages = await buildSite(options);
  console.log(`Generated ${pages.length} page(s).`);
}

main().catch((error: unknown) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
});
