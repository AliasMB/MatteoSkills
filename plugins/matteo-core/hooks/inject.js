// SessionStart: lo stdout entra nel contesto della sessione.
const fs = require('fs'), path = require('path');
process.stdout.write(fs.readFileSync(path.join(__dirname, 'matteo-habits.md'), 'utf8'));
