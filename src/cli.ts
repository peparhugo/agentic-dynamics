#!/usr/bin/env node
import { buildSite } from './generator';
import { serveSite } from './server';

function usage(): string {
  return 'Usage: ssg <build|serve> [--content <dir>] [--output <dir>] [--templates <dir>] [--port <port>]';
}

interface CliOptions {
  contentDir?: string;
  outputDir?: string;
  templateDir?: string;
  port?: number;
}

function options(args: string[], allowPort: boolean): CliOptions {
  const result: CliOptions = {};
  for (let index = 0; index < args.length; index += 1) {
    const value = args[index + 1];
    const option = args[index];
    if ((option === '--content' || option === '--output' || option === '--templates' || option === '--port') && (!value || value.startsWith('--'))) throw new Error(`Missing value for ${option}`);
    if (args[index] === '--content') result.contentDir = value;
    if (args[index] === '--output') result.outputDir = value;
    if (args[index] === '--templates') result.templateDir = value;
    if (option === '--port') {
      if (!allowPort) throw new Error(`Unknown option: ${option}`);
      const port = Number(value);
      if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('Port must be an integer between 1 and 65535');
      result.port = port;
    }
    if (option.startsWith('--') && option !== '--content' && option !== '--output' && option !== '--templates' && option !== '--port') throw new Error(`Unknown option: ${option}`);
  }
  return result;
}

async function main(): Promise<void> {
  const [command, ...args] = process.argv.slice(2);
  if (command === 'build') {
    const pages = await buildSite(options(args, false));
    console.log(`Generated ${pages.length} page(s).`);
    return;
  }
  if (command === 'serve') {
    const { port, ...buildOptions } = options(args, true);
    await serveSite({ ...buildOptions, port });
    return;
  }
  throw new Error(usage());
}

main().catch((error: unknown) => {
  console.error(error instanceof Error ? error.message : error);
  process.exitCode = 1;
});
