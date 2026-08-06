#!/usr/bin/env node

import { Command } from "commander";
import * as path from "path";
import { build } from "./build";
import { startDevServer } from "./server";
import { SiteConfig } from "./types";

const program = new Command();

program
  .name("ssg")
  .description("Static site generator from Markdown files")
  .version("1.0.0");

program
  .command("build")
  .description("Build the static site")
  .requiredOption("-s, --source <dir>", "Source directory of Markdown files")
  .requiredOption("-o, --output <dir>", "Output directory for generated HTML")
  .requiredOption("-t, --templates <dir>", "Template directory with Handlebars templates")
  .option("--title <title>", "Site title", "My Site")
  .option("--url <url>", "Site URL", "http://localhost:8080")
  .option("--description <desc>", "Site description", "")
  .action(async (options) => {
    const config: SiteConfig = {
      sourceDir: path.resolve(options.source),
      outputDir: path.resolve(options.output),
      templateDir: path.resolve(options.templates),
      siteTitle: options.title,
      siteUrl: options.url,
      siteDescription: options.description,
      port: 8080,
    };

    await build(config);
    console.log(`Site built to ${config.outputDir}`);
  });

program
  .command("serve")
  .description("Start dev server with live reload")
  .requiredOption("-s, --source <dir>", "Source directory of Markdown files")
  .requiredOption("-o, --output <dir>", "Output directory for generated HTML")
  .requiredOption("-t, --templates <dir>", "Template directory with Handlebars templates")
  .option("--title <title>", "Site title", "My Site")
  .option("--url <url>", "Site URL", "http://localhost:8080")
  .option("--description <desc>", "Site description", "")
  .option("-p, --port <port>", "Port to listen on", "8080")
  .action(async (options) => {
    const config: SiteConfig = {
      sourceDir: path.resolve(options.source),
      outputDir: path.resolve(options.output),
      templateDir: path.resolve(options.templates),
      siteTitle: options.title,
      siteUrl: options.url,
      siteDescription: options.description,
      port: parseInt(options.port, 10),
    };

    const server = await startDevServer(config);
    console.log(`Dev server running at http://localhost:${config.port}`);
    console.log(`Live reload watching ${config.sourceDir} and ${config.templateDir}`);

    process.on("SIGINT", () => {
      console.log("\nShutting down...");
      server.close();
      process.exit(0);
    });
  });

program.parse(process.argv);

export { SiteConfig, build, startDevServer };
