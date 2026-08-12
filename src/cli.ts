import { buildSite } from './generator';

function usage(): void {
  console.error('Usage: ssg build [--content <dir>] [--output <dir>] [--templates <dir>]');
}

function option(args: string[], name: string): string | undefined {
  const index = args.indexOf(name);
  if (index === -1) return undefined;
  const value = args[index + 1];
  if (!value || value.startsWith('--')) throw new Error(`Missing value for ${name}`);
  return value;
}

async function main(): Promise<void> {
  const args = process.argv.slice(2);
  if (args[0] !== 'build') {
    usage();
    process.exitCode = 1;
    return;
  }
  try {
    const pages = await buildSite({
      contentDir: option(args, '--content'),
      outputDir: option(args, '--output'),
      templatesDir: option(args, '--templates'),
    });
    console.log(`Built ${pages.length} page${pages.length === 1 ? '' : 's'}.`);
  } catch (error) {
    console.error(error instanceof Error ? error.message : error);
    process.exitCode = 1;
  }
}

void main();
