// Strategy: symlink site/public/highlights -> ../../highlights
// Astro copies public/ into dist/ and follows symlinks, so media files
// are served without duplicating ~345 MB on disk during development.

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const siteRoot = path.resolve(__dirname, "..");
const linkPath = path.join(siteRoot, "public", "highlights");
const targetPath = path.resolve(siteRoot, "..", "highlights");

function isValidSymlink(link, expectedTarget) {
  try {
    const stat = fs.lstatSync(link);
    if (!stat.isSymbolicLink()) return false;
    const resolved = fs.realpathSync(link);
    const expected = fs.realpathSync(expectedTarget);
    return resolved === expected;
  } catch {
    return false;
  }
}

if (!fs.existsSync(targetPath)) {
  console.warn(`Warning: highlights directory not found at ${targetPath}`);
}

fs.mkdirSync(path.dirname(linkPath), { recursive: true });

if (isValidSymlink(linkPath, targetPath)) {
  console.log("highlights symlink already valid");
} else {
  if (fs.existsSync(linkPath) || fs.lstatSync(linkPath, { throwIfNoEntry: false })) {
    fs.rmSync(linkPath, { recursive: true, force: true });
  }
  fs.symlinkSync(path.relative(path.dirname(linkPath), targetPath), linkPath, "dir");
  console.log(`Created symlink: ${linkPath} -> ../../highlights`);
}
