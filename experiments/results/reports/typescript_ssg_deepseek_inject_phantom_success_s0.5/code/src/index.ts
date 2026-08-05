#!/usr/bin/env node
import { parseArgs } from './cli';
import { generateSite } from './generator';
import { startDevServer } from './dev-server';

async function main() {
  const config = parseArgs(process.argv);

  if (config.devMode) {
    await startDevServer(config);
  } else {
    const pages = await generateSite(config);
    console.log(`Generated ${pages.length} pages in ${config.outputDir}`);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
