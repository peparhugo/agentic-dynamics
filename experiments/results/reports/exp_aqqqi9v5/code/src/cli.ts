#!/usr/bin/env node
import { Command } from "commander";
import type { SiteConfig } from "./types.js";
import { buildSite } from "./builder.js";
import { startDevServer } from "./server.js";

const program = new Command();

program
  .name("staticsite")
  .description("Static site generator")
  .version("1.0.0")
  .requiredOption("-s, --source <dir>", "source directory of markdown files")
  .requiredOption("-t, --templates <dir>", "template directory")
  .requiredOption("-o, --output <dir>", "output directory")
  .option("--title <title>", "site title", "My Site")
  .option("--description <desc>", "site description", "")
  .option("--base-url <url>", "base URL for RSS", "http://localhost:8080")
  .option("--serve", "start dev server with live reload")
  .option("--port <port>", "dev server port", "8080")
  .action(async (opts) => {
    const config: SiteConfig = {
      title: opts.title,
      description: opts.description,
      baseUrl: opts.baseUrl,
      sourceDir: opts.source,
      templateDir: opts.templates,
      outputDir: opts.output,
    };

    const rebuild = () => buildSite(config);

    if (opts.serve) {
      await rebuild();
      await startDevServer(
        config.outputDir,
        config.sourceDir,
        rebuild,
        parseInt(opts.port, 10),
      );
    } else {
      await buildSite(config);
    }
  });

program.parse();
