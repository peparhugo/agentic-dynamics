#!/usr/bin/env node
import { BuildResult } from './site';
import { ServeHandle } from './serve';
export interface CliOptions {
    command?: string;
    content?: string;
    output?: string;
    templates?: string;
    port?: number;
}
export declare function parseArgs(argv: string[]): CliOptions;
export declare function run(argv: string[]): BuildResult | Promise<ServeHandle>;
export declare function main(argv?: string[]): void;
