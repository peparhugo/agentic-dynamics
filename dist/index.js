#!/usr/bin/env node
import * as path from 'path';
import { SiteGenerator } from './generator.js';
import { DevServer } from './dev-server.js';
function parseArgs(args) {
    let command = 'build';
    let contentDir = './content';
    let outputDir = './dist';
    let templatesDir = './templates';
    let port = 3000;
    for (let i = 0; i < args.length; i++) {
        const arg = args[i];
        if (!arg.startsWith('-')) {
            command = arg;
            continue;
        }
        if (arg === '--content' && i + 1 < args.length) {
            contentDir = args[++i];
        }
        else if (arg === '--output' && i + 1 < args.length) {
            outputDir = args[++i];
        }
        else if (arg === '--templates' && i + 1 < args.length) {
            templatesDir = args[++i];
        }
        else if (arg === '--port' && i + 1 < args.length) {
            port = parseInt(args[++i], 10);
        }
    }
    return { command, contentDir, outputDir, templatesDir, port };
}
async function main() {
    const args = process.argv.slice(2);
    const { command, contentDir, outputDir, templatesDir, port } = parseArgs(args);
    const resolvedContentDir = path.resolve(contentDir);
    const resolvedOutputDir = path.resolve(outputDir);
    const resolvedTemplatesDir = path.resolve(templatesDir);
    try {
        if (command === 'build') {
            const generator = new SiteGenerator({
                contentDir: resolvedContentDir,
                outputDir: resolvedOutputDir,
                templatesDir: resolvedTemplatesDir,
            });
            await generator.build();
        }
        else if (command === 'serve') {
            const devServer = new DevServer({
                contentDir: resolvedContentDir,
                outputDir: resolvedOutputDir,
                templatesDir: resolvedTemplatesDir,
                port,
            });
            await devServer.start();
            process.on('SIGINT', async () => {
                console.log('\nShutting down server...');
                await devServer.stop();
                process.exit(0);
            });
        }
        else {
            console.error(`Unknown command: ${command}`);
            process.exit(1);
        }
    }
    catch (error) {
        console.error('Error:', error instanceof Error ? error.message : String(error));
        process.exit(1);
    }
}
main();
//# sourceMappingURL=index.js.map