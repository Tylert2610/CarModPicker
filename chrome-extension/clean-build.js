/**
 * Strip ES module syntax from built files, which Chrome extension service
 * workers do not support.
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const distDir = path.join(__dirname, 'dist');
const filesToClean = ['background.js', 'content.js', 'popup.js', 'options.js', 'types.js'];

/** Remove strict-mode, __esModule and empty export markers from one file. */
function cleanFile(filePath) {
  let content = fs.readFileSync(filePath, 'utf8');

  content = content.replace(/^"use strict";\s*\n?/gm, '');
  content = content.replace(/Object\.defineProperty\(exports,\s*"__esModule",\s*\{\s*value:\s*true\s*\}\);\s*\n?/g, '');
  content = content.replace(/^export\s+\{\s*\}\s*;?\s*$/gm, '');
  content = content.replace(/\n\s*export\s+\{\s*\}\s*;?\s*$/g, '');
  content = content.replace(/\n{3,}$/, '\n');

  fs.writeFileSync(filePath, content, 'utf8');
}

filesToClean.forEach(file => {
  const filePath = path.join(distDir, file);
  if (fs.existsSync(filePath)) {
    cleanFile(filePath);
  }
});
