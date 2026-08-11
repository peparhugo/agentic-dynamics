import { Page } from './types';
import { BuildCache } from './cache';
export declare function parseFile(filePath: string): Page;
export interface ParseStats {
    parsed: number;
    skipped: number;
}
export declare function parseDirectory(contentDir: string, cache?: BuildCache, stats?: ParseStats): Page[];
//# sourceMappingURL=parser.d.ts.map