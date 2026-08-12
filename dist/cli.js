"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.printHelp = printHelp;
exports.parseArgs = parseArgs;
exports.run = run;
const site_1 = require("./site");
const template_1 = require("./template");
function printHelp() {
    console.log([
        'Usage: ssg build [options]',
        '',
        'Generate a static site from Markdown files.',
        '',
        'Options:',
        '  --content <dir>    directory containing Markdown files (default: ./content)',
        '  --output <dir>     directory to write the generated site (default: ./dist)',
        '  --templates <dir>  directory containing templates (default: ./templates)',
        '  -h, --help         show this help message',
    ].join('\n'));
}
function parseArgs(argv) {
    const args = [...argv];
    let command = 'build';
    if (args.length > 0 && !args[0].startsWith('-')) {
        command = args.shift();
    }
    const options = {
        contentDir: site_1.DEFAULT_CONTENT_DIR,
        outputDir: site_1.DEFAULT_OUTPUT_DIR,
        templatesDir: template_1.DEFAULT_TEMPLATES_DIR,
    };
    for (let i = 0; i < args.length; i++) {
        const arg = args[i];
        if (arg === '--content' || arg === '-c') {
            const value = args[++i];
            if (value === undefined) {
                throw new Error(`missing value for ${arg}`);
            }
            options.contentDir = value;
        }
        else if (arg === '--output' || arg === '-o') {
            const value = args[++i];
            if (value === undefined) {
                throw new Error(`missing value for ${arg}`);
            }
            options.outputDir = value;
        }
        else if (arg === '--templates' || arg === '-t') {
            const value = args[++i];
            if (value === undefined) {
                throw new Error(`missing value for ${arg}`);
            }
            options.templatesDir = value;
        }
        else if (arg === '--help' || arg === '-h') {
            printHelp();
            process.exit(0);
        }
        else {
            throw new Error(`unknown argument: ${arg}`);
        }
    }
    return { command, options };
}
function run(argv) {
    let parsed;
    try {
        parsed = parseArgs(argv);
    }
    catch (err) {
        console.error(err instanceof Error ? err.message : String(err));
        process.exit(1);
    }
    if (parsed.command !== 'build') {
        console.error(`unknown command: ${parsed.command}`);
        process.exit(1);
    }
    try {
        const result = (0, site_1.buildSite)(parsed.options.contentDir, parsed.options.outputDir, parsed.options.templatesDir);
        const pagesWord = result.pages === 1 ? 'page' : 'pages';
        console.log(`Built ${result.pages} ${pagesWord} into ${result.outputDir}`);
    }
    catch (err) {
        console.error(err instanceof Error ? err.message : String(err));
        process.exit(1);
    }
}
