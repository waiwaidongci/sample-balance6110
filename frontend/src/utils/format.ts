export const number=(v:number|undefined|null,digits=2)=>v===undefined||v===null?'—':new Intl.NumberFormat('zh-CN',{maximumFractionDigits:digits}).format(v);
export const percent=(v:number|undefined)=>v===undefined?'—':(v*100).toFixed(2)+'%';
export const dateTime=(v:string)=>v.replace('T',' ').slice(0,16)+' UTC';
