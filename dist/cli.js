#!/usr/bin/env node
"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const commander_1 = require("commander");
const index_1 = require("./index");
const dev_server_1 = require("./dev-server");
const program = new commander_1.Command();
program
    .name("ssg")
    .description("Static site generator");
program
    .command("build")
    .description("Generate the static site")
    .option("--content <dir>", "Content directory", "./content")
    .option("--output <dir>", "Output directory", "./dist")
    .option("--templates <dir>", "Templates directory", "./templates")
    .action(async (options) => {
    try {
        await (0, index_1.build)({
            contentDir: options.content,
            outputDir: options.output,
            templatesDir: options.templates,
        });
        console.log("Build complete");
    }
    catch (err) {
        console.error("Error:", err.message);
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
    .action(async (options) => {
    try {
        await (0, dev_server_1.startDevServer)({
            contentDir: options.content,
            outputDir: options.output,
            templatesDir: options.templates,
            port: parseInt(options.port, 10),
        });
    }
    catch (err) {
        console.error("Error:", err.message);
        process.exit(1);
    }
});
program.parse();
