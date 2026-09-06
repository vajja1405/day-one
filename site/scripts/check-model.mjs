import assert from 'node:assert/strict';
import {calculate,validateScenario} from '../app/agent-tools.ts';
const defaults={members:157309,cohort:28,pmpm:70,information:33,acceleration:50};
assert.ok(Math.abs(calculate(validateScenario(defaults)).annualized_gross_opportunity-6104847.672)<1e-6);
for(const key of Object.keys(defaults))assert.equal(calculate({...defaults,[key]:0}).annualized_gross_opportunity,0);
for(const bad of [{...defaults,information:-1},{...defaults,members:NaN},{...defaults,pmpm:Infinity},{...defaults,information:101},{...defaults,cohort:1.5},{...defaults,extra:1},null])assert.throws(()=>validateScenario(bad));
console.log('Scenario arithmetic and invalid-input checks passed. Browser WebMCP registration was not tested.');
