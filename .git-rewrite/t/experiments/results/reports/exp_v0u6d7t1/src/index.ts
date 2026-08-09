#!/usr/bin/env node
import { Command } from "commander";
import path from "node:path";
import type { CLIOptions } from "./types.js";
import { build } from "./build.js";
import { serve } from "./server.js";

const program = new Command();

program
  .name("statik")
  .description("Static site generator from Markdown + Handlebars")
  .option("-s, --source <dir>", "source directory of Markdown files", "content")
  .option("-t, --templates <dir>", "templates directory", "templates")
  .option("-o, --output <dir>", "output directory for generated HTML", "public")
  .option("--serve", "start a dev server with live reload")
  .option("-p, --port <number>", "dev server port", "3000")
  .option("--site-title <title>", "site title (used in feeds)", "My Site")
  .option("--site-url <url>", "site URL (used in feeds)", "http://localhost:3000")
  .parse(process.argv);

async function main() {
  const opts: CLIOptions = {
    source: path.resolve(program.opts().source),
    templates: path.resolve(program.opts().templates),
    output: path.resolve(program.opts().output),
    serve: program.opts().serve,
    port: parseInt(program.opts().port, 10),
    siteTitle: program.opts().siteTitle,
    siteUrl: program.opts().siteUrl,
  };

  if (opts.serve) {
    await serve(opts);
  } else {
    console.log(`Building site from ${opts.source}...`);
    await build(opts);
    console.log(`Site built to ${opts.output}`);
  }
}

main().catch((err) => {
  console.error("Error:", err.message);
  process.exit(1);
});
