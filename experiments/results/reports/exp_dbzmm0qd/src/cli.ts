#!/usr/bin/env node
import { Command } from "commander";
import { resolve } from "node:path";
import { build } from "./build.js";
import { startDevServer } from "./dev-server.js";
import { startWatcher } from "./watcher.js";

const program = new Command();

program
  .name("ssg")
  .description("Static site generator")
  .option("-s, --source <dir>", "source directory of Markdown files", "content")
  .option("-t, --templates <dir>", "template directory of Handlebars files", "templates")
  .option("-o, --output <dir>", "output directory for generated HTML", "public")
  .option("--site-title <title>", "site title", "My Site")
  .option("--site-url <url>", "site base URL", "http://localhost:3000");

program
  .command("build")
  .description("Build the static site")
  .action(() => {
    const opts = program.opts();
    const config = {
      sourceDir: resolve(opts.source),
      templateDir: resolve(opts.templates),
      outputDir: resolve(opts.output),
      siteTitle: opts.siteTitle,
      siteUrl: opts.siteUrl,
    };
    build(config);
    console.log(`Site built to ${config.outputDir}`);
  });

program
  .command("dev")
  .description("Start dev server with live reload")
  .option("-p, --port <port>", "port to listen on", "3000")
  .action((cmdOpts) => {
    const opts = program.opts();
    const config = {
      sourceDir: resolve(opts.source),
      templateDir: resolve(opts.templates),
      outputDir: resolve(opts.output),
      siteTitle: opts.siteTitle,
      siteUrl: `http://localhost:${cmdOpts.port}`,
    };
    startDevServer(config, parseInt(cmdOpts.port, 10));
    startWatcher(config);
  });

program.parse();
