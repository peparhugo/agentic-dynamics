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
    if (option !== '--content' && option !== '--output') {
      usage(); process.exitCode = 1; return;
    }
    const value = args[++index];
    if (!value) { usage(); process.exitCode = 1; return; }
    if (option === '--content') options.contentDir = value;
    else options.outputDir = value;
  }
  await buildSite(options);
}

if (require.main === module) {
  main().catch((error: unknown) => { console.error(error instanceof Error ? error.message : error); process.exitCode = 1; });
}
