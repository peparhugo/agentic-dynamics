export interface MarkdownFile {
    name: string;
    path: string;
    content: string;
}
export declare function readMarkdownFiles(contentDir: string): Promise<MarkdownFile[]>;
export declare function writeFile(filePath: string, content: string): Promise<void>;
export declare function ensureDir(dirPath: string): Promise<void>;
//# sourceMappingURL=files.d.ts.map