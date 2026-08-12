"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const cli_1 = require("../cli");
describe('parseArgs', () => {
    it('parses the build command with defaults', () => {
        const result = (0, cli_1.parseArgs)(['build']);
        expect(result.command).toBe('build');
        expect(result.options.contentDir).toBe('./content');
        expect(result.options.outputDir).toBe('./dist');
        expect(result.error).toBeUndefined();
    });
    it('parses --content and --output', () => {
        const result = (0, cli_1.parseArgs)(['build', '--content', 'posts', '--output', 'public']);
        expect(result.command).toBe('build');
        expect(result.options.contentDir).toBe('posts');
        expect(result.options.outputDir).toBe('public');
    });
    it('handles options before the command', () => {
        const result = (0, cli_1.parseArgs)(['--output', 'out', 'build']);
        expect(result.command).toBe('build');
        expect(result.options.outputDir).toBe('out');
    });
    it('returns an error when a value is missing', () => {
        const result = (0, cli_1.parseArgs)(['build', '--content']);
        expect(result.error).toBe('Missing value for --content');
    });
});
