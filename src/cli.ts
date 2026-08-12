#!/usr/bin/env node
import { buildSite } from './generator';

function usage(): void {
  console.error('Usage: ssg build [--content <dir>] [--output <dir>]');
}

export async function main(args: string[] = process.argv.slice(2)): Promise<void> {
  if (args[0] !== 'build') {
    usage();
    process.exitCode = 1;
    return;
  }
  const options: { contentDir?: string; outputDir?: string } = {};
  for (let index = 1; index < args.length; index += 1) {
    const option = args[index];
    if (option === '--content' || option === '--output') {
      const value = args[index + 1];
      if (!value) throw new Error(`${option} requires a directory`);
      if (option === '--content') options.contentDir = value;
      else options.outputDir = value;
      index += 1;
    } else {
      throw new Error(`Unknown option: ${option}`);
    }
  }
  const pages = await buildSite(options);
  console.log(`Built ${pages.length} page${pages.length === 1 ? '' : 's'}.`);
}

if (require.main === module) {
  main().catch((error: unknown) => {
    console.error(error instanceof Error ? error.message : error);
    process.exitCode = 1;
  });
}
