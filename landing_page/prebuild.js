const fs = require('fs');
const path = require('path');

const packagePath = path.join(__dirname, 'package.json');
const package = JSON.parse(fs.readFileSync(packagePath, 'utf-8'));

// Increment version - this example simply increments the patch version
const versionParts = package.version.split('.');
versionParts[2] = parseInt(versionParts[2]) + 1; // Increment patch number
const newVersion = versionParts.join('.');

package.version = newVersion;
fs.writeFileSync(packagePath, JSON.stringify(package, null, 2));

// Optionally, export the new version to an environment variable
// Note: This may vary depending on your OS and shell
process.env.VERSION = newVersion;
console.log(`Version updated to ${newVersion}`);
