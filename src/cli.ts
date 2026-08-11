#!/usr/bin/env node
import { Command } from "commander";
import { build } from "./index";
import { startDevServer } from "./dev-server";

const program = new Command();

program
  .name("ssg")
  .description("Static site generator");

program
  .command("build")
  .description("Generate the static site")
  .option("--content <dir>", "Content directory", "./content")
  .option("--output <dir>", "Output directory", "./dist")
  .option("--templates <dir>", "Templates directory", "./templates")
  .option("--config <file>", "Config file", "ssg.config.ts")
  .action(async (options: { content: string; output: string; templates: string; config: string }) => {
    try {
      await build({
        contentDir: options.content,
        outputDir: options.output,
        templatesDir: options.templates,
      });
      console.log("Build complete");
    } catch (err) {
      console.error("Error:", (err as Error).message);
      process.exit(1);
    }
  });

program
  .command("serve")
  .description("Start dev server with live reload")
  .option("--content <dir>", "Content directory", "./content")
  .option("--output <dir>", "Output directory", "./dist")
  .option("--templates <dir>", "Templates directory", "./templates")
  .option("--port <number>", "Port to listen on", "3000")
  .option("--config <file>", "Config file", "ssg.config.ts")
  .action(async (options: { content: string; output: string; templates: string; port: string; config: string }) => {
    try {
      await startDevServer({
        contentDir: options.content,
        outputDir: options.output,
        templatesDir: options.templates,
        port: parseInt(options.port, 10),
      });
    } catch (err) {
      console.error("Error:", (err as Error).message);
      process.exit(1);
    }
  });

program.parse();
