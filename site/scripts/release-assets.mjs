import {copyFileSync,writeFileSync} from 'node:fs';
copyFileSync('../day-one-offline.html','dist/day-one-offline.html');
writeFileSync('dist/.nojekyll','');
console.log('Included the original self-contained offline backup and .nojekyll.');
