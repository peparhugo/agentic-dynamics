export function parseArgs(argv) {
    const args = {
        command: 'build',
        contentDir: './content',
        outputDir: './dist'
    };
    for (let i = 0; i < argv.length; i++) {
        const arg = argv[i];
        if (arg === '--content' && i + 1 < argv.length) {
            args.contentDir = argv[++i];
        }
        else if (arg === '--output' && i + 1 < argv.length) {
            args.outputDir = argv[++i];
        }
        else if (arg === '--port' && i + 1 < argv.length) {
            args.port = parseInt(argv[++i], 10);
        }
        else if (arg === 'build') {
            args.command = 'build';
        }
        else if (arg === 'serve') {
            args.command = 'serve';
        }
    }
    return args;
}
//# sourceMappingURL=cli.js.map