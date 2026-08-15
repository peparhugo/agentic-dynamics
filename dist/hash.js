"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.hashString = hashString;
exports.hashFile = hashFile;
const crypto_1 = __importDefault(require("crypto"));
const fs_1 = __importDefault(require("fs"));
/**
 * Computes a stable SHA-256 digest for an in-memory string. Used to build the
 * incremental-build fingerprint for page sources and templates.
 */
function hashString(value) {
    return crypto_1.default.createHash('sha256').update(value).digest('hex');
}
/** Computes a SHA-256 digest for the UTF-8 contents of a file. */
function hashFile(filePath) {
    return hashString(fs_1.default.readFileSync(filePath, 'utf-8'));
}
