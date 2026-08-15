import { Post } from './types';
export interface BuildOptions {
    contentDir: string;
    outputDir: string;
}
export interface BuildResult {
    posts: Post[];
    filesWritten: string[];
    outputDir: string;
}
export declare function buildSite(options: BuildOptions): BuildResult;
