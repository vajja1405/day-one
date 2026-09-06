import {readFileSync,writeFileSync} from 'node:fs';
const js=readFileSync('offline-dist/day-one.js','utf8').replaceAll('</script','<\\/script');
const css=readFileSync('offline-dist/day-one.css','utf8').replaceAll('</style','<\\/style');
const html='<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Day One — Offline synthetic prototype</title><style>'+css+'</style></head><body><div id="root"></div><script>'+js+'</script></body></html>';
writeFileSync('offline-dist/day-one-offline.html',html);
console.log('Created standalone day-one-offline.html with all data and assets embedded.');
