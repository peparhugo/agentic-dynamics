#!/usr/bin/env node

import { Command } from "commander";
import * as path from "path";
import { Generator } from "./generator";
import { GeneratorConfig } from "./types";
import { startServer } from "./server";
import { watch } from "./watcher";

const program = new Command();

program
  .name("triton")
  .description("Static site generator")
  .version("1.0.0")
  .option("-s, --source <dir>", "Source directory of Markdown files", "source")
  .option("-t, --templates <dir>", "Template directory of Handlebars files", "templates")
  .option("-o, --output <dir>", "Output directory for generated HTML", "public")
  .option("--title <title>", "Site title", "My Site")
  .option("--url <url>", "Site URL", "http://localhost:3000")
  .option("-d, --dev", "Start development server with live reload", false)
  .option("-p, --port <port>", "Dev server port", "3000")
  .action((options) => {
    const config: GeneratorConfig = {
      sourceDir: path.resolve(options.source),
      templateDir: path.resolve(options.templates),
      outputDir: path.resolve(options.output),
      siteTitle: options.title,
      siteUrl: options.url,
      dev: options.dev,
      port: parseInt(options.port, 10),
    };

    const generator = new Generator(config);
    generator.build();

    if (config.dev) {
      const { server, reload } = startServer(config.port, config.outputDir);

      const stopWatch = watch(config, reload);

      process.on("SIGINT", () => {
        stopWatch();
        server.close();
        process.exit(0);
      });

      process.on("SIGTERM", () => {
        stopWatch();
        server.close();
        process.exit(0);
      });
    }
  });

program.parse(process.argv);
