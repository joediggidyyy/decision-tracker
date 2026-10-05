// Preserve exact request identity when a response is lost.
export const definitive=error=>!!error.code&&error.code!=='INTERNAL_ERROR';
export async function readResponse(response){
 try{return await response.json();}
 catch{throw Error('The server response could not be read. If you were saving, the outcome is unknown; retry the retained request.');}
}
export async function sendRetained(edit,payload,send){
 const encoded=JSON.stringify(payload);
 if(edit.pending&&edit.pending!==encoded)throw Error('A prior request may have committed. Retry the original save before changing the draft.');
 edit.pending=encoded;
 try{return await send(JSON.parse(encoded));}
 catch(error){if(error.code)throw error;return await send(JSON.parse(encoded));}
}
