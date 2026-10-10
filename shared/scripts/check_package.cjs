const reader=require('../../viewer/package-reader.js');
const JSZip=require('../../viewer/vendor/jszip/dist/jszip.min.js');
if(!globalThis.crypto)globalThis.crypto=require('node:crypto').webcrypto;
let chunks=[];process.stdin.on('data',chunk=>chunks.push(chunk));
process.stdin.on('end',async()=>{
 try {await reader.readPackage(new Uint8Array(Buffer.concat(chunks)),{JSZip});}
 catch(error){process.stderr.write(error.message);process.exitCode=1;}
});
