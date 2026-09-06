import {readFileSync,writeFileSync} from 'node:fs';
const dir='public/data/';
const read=name=>JSON.parse(readFileSync(dir+name+'.json','utf8'));
const members=read('members');
if(members.length!==12)throw new Error('Expected 12 synthetic members.');
const data={members,briefs:{},records:{},audits:{},evaluation:read('evaluation'),audit:read('audit_sample')};
for(const m of members){for(const key of ['briefs','records','audits'])data[key][m.member_id]=read(key+'/'+m.member_id);}
if(data.evaluation.summary.cases!==30||data.evaluation.summary.unsafe_suggestion_rate!==0)throw new Error('Evaluation contract failed.');
writeFileSync('app/demo-data.json',JSON.stringify(data));
console.log('Bundled 12 synthetic records, briefs, audits and 30 evaluation cases.');
