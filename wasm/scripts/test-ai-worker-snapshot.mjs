import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const header=fs.readFileSync(new URL('../../source/simulation2/helpers/AIWorkerScript.h',import.meta.url),'utf8');
const script=name=>new RegExp(name+'\\[\\] = R"AIJS\\(([\\s\\S]*?)\\)AIJS"').exec(header)[1];
const requirements=fs.readFileSync(new URL('../../binaries/data/mods/public/simulation/helpers/Requirements.js',import.meta.url),'utf8');
function fixture(dense=false,supply={amount:123,gatherers:2}){
  const tech={classCounts:{Village:2},typeCountsByClass:{Village:{a:1,b:1}},
    researchedTechs:new Set(['phase_town']),GetResearchedTechs(){return this.researchedTechs;},
    IsTechnologyResearched(name){return this.researchedTechs.has(name);}};
  const orders=[{type:'Gather',data:{target:19,metadata:{role:'worker'}}}];
  const modifiers=[];
  const queries=[];
  const sim=vm.createContext({SYSTEM_ENTITY:0,IID_AIProxy:'AIProxy',IID_PlayerManager:'PlayerManager',
    IID_UnitAI:'UnitAI',IID_ResourceSupply:'ResourceSupply',IID_ResourceGatherer:'ResourceGatherer',
    IID_ModifiersManager:'ModifiersManager',IID_TechnologyManager:'TechnologyManager',
    QueryPlayerIDInterface:()=>tech,
    Engine:{RegisterGlobal(name,value){sim[name]=value;},
      GetEntitiesWithInterface:iid=>({AIProxy:[10,19,20],UnitAI:[10,88],ResourceSupply:[19],ResourceGatherer:[10]}[iid] || []),
      QueryInterface(id,iid){
        queries.push([id,iid]);
        if(iid==='PlayerManager')return {GetAllPlayers:()=>[1]};
        if(iid==='ModifiersManager')return {AddModifiers:(...args)=>modifiers.push(args)};
        if(id===10&&iid==='UnitAI')return {GetOrders:()=>orders};
        if(id===10&&iid==='ResourceGatherer')return {GetCarryingStatus:()=>[{type:'wood',amount:7}]};
        if(id===19&&iid==='ResourceSupply')return {GetCurrentAmount:()=>supply.amount,GetNumGatherers:()=>supply.gatherers};
        return null;
      }}});
  vm.runInContext(requirements,sim);
  vm.runInContext(script(dense?'AIWorkerCaptureDense':'AIWorkerCapture'),sim);
  const snapshot=structuredClone(vm.runInContext('__captureAIWorkerSnapshot()',sim));
  const worker=vm.createContext({snapshot});
  vm.runInContext(script('AIWorkerInstall'),worker);
  vm.runInContext('__installAIWorkerSnapshot(snapshot)',worker);
  return {sim,worker,tech,orders,modifiers,queries};
}

test('reused capture function reads fresh state without retaining a previous snapshot',()=>{
  const {sim,orders}=fixture();
  const capture=vm.runInContext('__captureAIWorkerSnapshot',sim);
  const before=structuredClone(vm.runInContext('__captureAIWorkerSnapshot()',sim));
  orders[0].data.target=42;
  const after=structuredClone(vm.runInContext('__captureAIWorkerSnapshot()',sim));
  assert.equal(capture,vm.runInContext('__captureAIWorkerSnapshot',sim));
  assert.notEqual(before.entities,after.entities);
  assert.equal(before.entities[10].orders[0].data.target,19);
  assert.equal(after.entities[10].orders[0].data.target,42);
});

test('component enumeration captures each present interface once and excludes non-AI owners',()=>{
  const {sim,worker,queries}=fixture();
  assert.deepEqual(queries.filter(([id])=>id!==0),[[10,'UnitAI'],[19,'ResourceSupply'],[10,'ResourceGatherer']]);
  assert.equal(vm.runInContext('SimEngine.QueryInterface(20,Sim.IID_UnitAI)',worker),null);
  assert.equal(vm.runInContext('SimEngine.QueryInterface(88,Sim.IID_UnitAI)',worker),null);
  assert.equal(vm.runInContext('Object.keys(snapshot.entities).join(",")',worker),'10,19,20');
});

test('dense supply snapshot retains values, absence, and owned clone storage',()=>{
  const {worker,orders}=fixture(true);
  orders[0].data.target=999;
  assert.equal(vm.runInContext('SimEngine.QueryInterface(10,Sim.IID_UnitAI).GetOrders()[0].data.target',worker),19);
  assert.equal(vm.runInContext('SimEngine.QueryInterface(19,Sim.IID_ResourceSupply).GetCurrentAmount()',worker),123);
  assert.equal(vm.runInContext('SimEngine.QueryInterface(19,Sim.IID_ResourceSupply).GetNumGatherers()',worker),2);
  assert.equal(vm.runInContext('SimEngine.QueryInterface(20,Sim.IID_ResourceSupply)',worker),null);
  assert.equal(vm.runInContext('SimEngine.QueryInterface(88,Sim.IID_ResourceSupply)',worker),null);
  assert.equal(vm.runInContext('snapshot.supplies.byteLength',worker),16);
});

test('dense supply snapshot preserves binary64 values and nonnumeric fallback',()=>{
  for(const amount of [Infinity,NaN,-0,1/3,undefined,'custom']){
    const supply={amount,gatherers:7};
    const {worker}=fixture(true,supply);supply.amount=999;
    assert.ok(Object.is(vm.runInContext('SimEngine.QueryInterface(19,Sim.IID_ResourceSupply).GetCurrentAmount()',worker),amount));
    assert.equal(vm.runInContext('SimEngine.QueryInterface(19,Sim.IID_ResourceSupply).GetNumGatherers()',worker),7);
  }
});

test('snapshot getters retain exact order fields and never read subsequent simulation mutations',()=>{
  const {worker,orders}=fixture();orders[0].data.target=999;
  assert.equal(vm.runInContext('SimEngine.QueryInterface(10,Sim.IID_UnitAI).GetOrders()[0].data.target',worker),19);
  assert.equal(vm.runInContext('SimEngine.QueryInterface(19,Sim.IID_ResourceSupply).GetCurrentAmount()',worker),123);
  assert.equal(vm.runInContext('SimEngine.QueryInterface(19,Sim.IID_ResourceSupply).GetNumGatherers()',worker),2);
  assert.equal(vm.runInContext('SimEngine.QueryInterface(10,Sim.IID_ResourceGatherer).GetCarryingStatus()[0].amount',worker),7);
  assert.equal(vm.runInContext('SimEngine.QueryInterface(10,Sim.IID_ResourceSupply)',worker),null);
  assert.throws(()=>vm.runInContext('SimEngine.QueryInterface(10,"Health")',worker),/Unsupported/);
});
test('original requirements implementation runs identically on cloned technology state',()=>{
  const {sim,worker,tech}=fixture();
  for(const requirement of [{},{Entities:{Village:{Count:2}}},{Entities:{Village:{Variants:3}}},
      {Techs:{_string:'phase_town !phase_city'}},{All:{Entities:{Village:{Count:2}},Techs:{_string:'phase_town'}}},
      {Any:{Entities:{Village:{Count:100}},Techs:{_string:'phase_town'}}}]){
    sim.input=requirement;worker.input=structuredClone(requirement);
    assert.equal(vm.runInContext('Sim.RequirementsHelper.AreRequirementsMet(input,1)',worker),
      vm.runInContext('RequirementsHelper.AreRequirementsMet(input,1)',sim));
  }
  tech.classCounts.Village=0;
  assert.equal(vm.runInContext('Sim.RequirementsHelper.AreRequirementsMet({Entities:{Village:{Count:2}}},1)',worker),true);
});
test('initialization effects are explicit, ordered and applied only by the simulation owner',()=>{
  const {sim,worker,modifiers}=fixture();
  const call='SimEngine.QueryInterface(Sim.SYSTEM_ENTITY,Sim.IID_ModifiersManager).AddModifiers("AI Bonus",{speed:1.25},10)';
  assert.throws(()=>vm.runInContext(call,worker),/outside initialization/);
  vm.runInContext('__aiAllowEffects=true',worker);vm.runInContext(call,worker);
  assert.equal(modifiers.length,0);
  // Match the temporary, mutable property defined by the C++ bridge.
  Object.defineProperty(sim,'__aiWorkerEffects',{value:structuredClone(vm.runInContext('__aiEffects.splice(0)',worker)),writable:true,configurable:true});
  vm.runInContext(script('AIWorkerApplyEffects'),sim);
  assert.equal(modifiers.length,1);assert.equal(modifiers[0][2],10);
  assert.equal(vm.runInContext('__aiEffects.length',worker),0);
  assert.equal(vm.runInContext('__aiWorkerEffects',sim),undefined);
  sim.__aiWorkerEffects=[];
  vm.runInContext(script('AIWorkerApplyEffects'),sim);
  assert.equal(modifiers.length,1);
});
