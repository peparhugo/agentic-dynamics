#!/usr/bin/env node
import { Command } from "commander";
import { build } from "./builder.js";
import { startDevServer } from "./server.js";

const program = new Command();

program
  .name("staticsite")
  .description("Static site generator")
  .version("1.0.0")
  .requiredOption("--source <dir>", "Source directory of markdown files")
  .requiredOption("--templates <dir>", "Template directory of handlebars files")
  .requiredOption("--output <dir>", "Output directory for generated HTML")
  .option("--base-url <url>", "Base URL for RSS feed", "http://localhost:3000")
  .option("--site-title <title>", "Site title", "My Site")
  .option("--site-description <desc>", "Site description", "A static site")
  .option("--author <name>", "Site author")
  .option("--dev", "Start dev server with live reload")
  .option("--port <port>", "Dev server port", "3000");

program.parse();

const opts = program.opts();

const buildOpts = {
  source: opts.source,
  templates: opts.templates,
  output: opts.output,
  baseUrl: opts.baseUrl,
  siteTitle: opts.siteTitle,
  siteDescription: opts.siteDescription,
  author: opts.author,
  includeDrafts: !!opts.dev,
};

if (opts.dev) {
  const port = parseInt(opts.port, 10);
  const server = startDevServer(
    opts.output,
    [opts.source, opts.templates],
    port,
    () => build(buildOpts)
  );
  console.log(`Dev server running at http://localhost:${port}`);
  console.log("Watching for changes...");
} else {
  build(buildOpts);
  console.log(`Site built to ${opts.output}`);
}
