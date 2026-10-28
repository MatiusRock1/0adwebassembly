"""Real network commands and original component assertions, without mocks."""
import json
from phase4_flow import checkpoint

BOOTSTRAP = r'''(()=>{
  const own=Engine.GuiInterfaceCall("GetPlayerEntities",{}).map(id=>Engine.GuiInterfaceCall("GetEntityState",id));
  const cc=own.find(entity=>entity.template==="structures/athen/civil_centre");
  const workers=own.filter(entity=>entity.builder && entity.unitAI);
  if(!cc || workers.length<6)throw new Error("Original starting entities missing");
  const gaia=Engine.PickPlayerEntitiesOnScreen(0).map(id=>Engine.GuiInterfaceCall("GetEntityState",id));
  const distance=entity=>(entity.position.x-cc.position.x)**2+(entity.position.z-cc.position.z)**2;
  const food=gaia.filter(entity=>entity.position && entity.resourceSupply?.type.generic==="food" && entity.resourceSupply.type.specific==="fruit").sort((a,b)=>distance(a)-distance(b))[0];
  if(!food)throw new Error("Original food resource missing");
  const player=Engine.GuiInterfaceCall("GetSimulationState",{}).players[1];
  globalThis.phase4Systems={cc,workers,food,initialPop:player.popCount,initialPopLimit:player.popLimit};
  return JSON.stringify(phase4Systems);
})()'''

ORDERS = r'''(()=>{
  const {cc,workers,food}=phase4Systems;
  const commands=[
    {type:"walk",entities:[workers[0].id],x:cc.position.x+8,z:cc.position.z+8,queued:false},
    {type:"gather",entities:[workers[1].id],target:food.id,queued:false},
    {type:"set-rallypoint",structures:[cc.id],x:cc.position.x+5,z:cc.position.z+20,data:{command:"walk"},queued:false},
    {type:"train",entities:[cc.id],template:cc.trainer.entities.find(name=>name.includes("support_civilian")),count:2,metadata:null},
    {type:"diplomacy",player:2,to:"neutral"}
  ];
  for(const command of commands)Engine.PostNetworkCommand(command);
  const builders=workers.slice(2,6).map(entity=>entity.id);
  for(let radius=20;radius<=50;radius+=5){
    for(let direction=0;direction<16;direction++){
      const angle=direction*Math.PI/8;
      const x=cc.position.x+Math.cos(angle)*radius,z=cc.position.z+Math.sin(angle)*radius;
      const preview=Engine.GuiInterfaceCall("SetBuildingPlacementPreview",{template:"structures/athen/house",x,z,angle:0,actorSeed:0});
      if(!preview.success)continue;
      const command={type:"construct",entities:builders,template:"structures/athen/house",x,z,angle:0,autorepair:true,autocontinue:false,queued:false,actorSeed:0};
      Engine.PostNetworkCommand(command);commands.push(command);
      phase4Systems.housePosition={x,z};
      Engine.GuiInterfaceCall("SetBuildingPlacementPreview",{template:""});
      return JSON.stringify(commands);
    }
  }
  throw new Error("No valid original construction placement");
})()'''

STATE = r'''(()=>{
  const sim=Engine.GuiInterfaceCall("GetSimulationState",{});
  const own=Engine.GuiInterfaceCall("GetPlayerEntities",{}).map(id=>Engine.GuiInterfaceCall("GetEntityState",id));
  const cc=own.find(entity=>entity.id===phase4Systems.cc.id);
  const walker=own.find(entity=>entity.id===phase4Systems.workers[0].id);
  return JSON.stringify({sim,cc,walker,houses:own.filter(entity=>entity.template==="structures/athen/house" && !entity.foundation),ownCount:own.length});
})()'''


def run_systems(gui, save):
    result = dict(passed=False, commands=[], assertions={})
    state = checkpoint(gui, 10000)
    save('initial', 10000, state)
    setup = json.loads(gui(BOOTSTRAP))
    result['setup'] = setup
    result['commands'] = json.loads(gui(ORDERS))
    state = checkpoint(gui, 70000)
    save('economy-construction-production', 70000, state)
    observed = json.loads(gui(STATE))
    result['economy'] = observed
    assertions = result['assertions']
    assertions['gathering'] = observed['sim']['players'][1]['statistics']['resourcesGathered']['food'] > 0
    assertions['construction'] = len(observed['houses']) >= 1 and observed['sim']['players'][1]['popLimit'] > setup['initialPopLimit']
    assertions['production'] = observed['sim']['players'][1]['popCount'] >= setup['initialPop'] + 2
    assertions['diplomacy'] = observed['sim']['players'][1]['isNeutral'][2]
    assertions['movement'] = observed['walker']['position'] != setup['workers'][0]['position']
    assertions['rallyPoint'] = observed['cc']['rallyPoint']['position'] == dict(x=setup['cc']['position']['x']+5,z=setup['cc']['position']['z']+20)
    if not all(assertions.values()):
        raise RuntimeError('Original command assertions failed: ' + json.dumps(assertions))
    garrison_id = setup['workers'][0]['id']
    gui('Engine.PostNetworkCommand(' + json.dumps(dict(type='garrison',entities=[garrison_id],target=setup['cc']['id'],queued=False)) + '); "queued"')
    state = checkpoint(gui, 80000)
    save('garrison', 80000, state)
    observed = json.loads(gui(STATE))
    assertions['garrison'] = garrison_id in observed['cc']['garrisonHolder']['entities']
    if not assertions['garrison']:
        raise RuntimeError('Original garrison command did not complete.')
    gui('Engine.PostNetworkCommand(' + json.dumps(dict(type='unload',entities=[garrison_id],garrisonHolder=setup['cc']['id'])) + '); "queued"')
    state = checkpoint(gui, 90000)
    save('unload', 90000, state)
    observed = json.loads(gui(STATE))
    assertions['unload'] = garrison_id not in observed['cc']['garrisonHolder']['entities'] and 'position' in observed['walker']
    if not assertions['unload']:
        raise RuntimeError('Original unload command did not complete.')
    result['passed'] = True
    return result


ADVANCED_BOOT = r'''(()=>{
  const {cc,workers}=phase4Systems;
  const own=Engine.GuiInterfaceCall("GetPlayerEntities",{}).map(id=>Engine.GuiInterfaceCall("GetEntityState",id));
  const known=new Set(workers.map(entity=>entity.id));
  const woodcutters=[...workers.slice(6),...own.filter(entity=>entity.builder && entity.unitAI && !known.has(entity.id))].map(entity=>entity.id);
  const trees=Engine.PickPlayerEntitiesOnScreen(0).map(id=>Engine.GuiInterfaceCall("GetEntityState",id)).filter(entity=>entity.position && entity.resourceSupply?.type.generic==="wood");
  trees.sort((a,b)=>(a.position.x-cc.position.x)**2+(a.position.z-cc.position.z)**2-((b.position.x-cc.position.x)**2+(b.position.z-cc.position.z)**2));
  if(!trees.length || woodcutters.length<4)throw new Error("Original wood gathering setup missing");
  Engine.PostNetworkCommand({type:"gather",entities:woodcutters,target:trees[0].id,queued:false});
  Engine.PostNetworkCommand({type:"research",entity:cc.id,template:"unlock_shared_los",metadata:null});
  const planned=[];
  for(let radius=20;radius<=60 && planned.length<4;radius+=5){
    for(let direction=0;direction<32 && planned.length<4;direction++){
      const angle=direction*Math.PI/16,x=cc.position.x+Math.cos(angle)*radius,z=cc.position.z+Math.sin(angle)*radius;
      if(planned.some(position=>(position.x-x)**2+(position.z-z)**2<20**2))continue;
      const preview=Engine.GuiInterfaceCall("SetBuildingPlacementPreview",{template:"structures/athen/house",x,z,angle:0,actorSeed:0});
      if(!preview.success)continue;
      const command={type:"construct",entities:workers.slice(2,6).map(entity=>entity.id),template:"structures/athen/house",x,z,angle:0,autorepair:true,autocontinue:false,queued:true,actorSeed:0};
      Engine.PostNetworkCommand(command);planned.push({x,z});
    }
  }
  Engine.GuiInterfaceCall("SetBuildingPlacementPreview",{template:""});
  if(planned.length!==4)throw new Error("Four legal village building positions required");
  return JSON.stringify({woodcutters,tree:trees[0].id,planned});
})()'''

MARKETS = r'''(()=>{
  const {cc,workers}=phase4Systems,planned=[];
  for(let radius=40;radius<=70 && planned.length<2;radius+=5){
    for(let direction=0;direction<32 && planned.length<2;direction++){
      const angle=direction*Math.PI/16,x=cc.position.x+Math.cos(angle)*radius,z=cc.position.z+Math.sin(angle)*radius;
      if(planned.some(position=>(position.x-x)**2+(position.z-z)**2<70**2))continue;
      const preview=Engine.GuiInterfaceCall("SetBuildingPlacementPreview",{template:"structures/athen/market",x,z,angle:0,actorSeed:0});
      if(!preview.success)continue;
      Engine.PostNetworkCommand({type:"construct",entities:workers.slice(2,6).map(entity=>entity.id),template:"structures/athen/market",x,z,angle:0,autorepair:true,autocontinue:false,queued:true,actorSeed:0});
      planned.push({x,z});
    }
  }
  Engine.GuiInterfaceCall("SetBuildingPlacementPreview",{template:""});
  if(planned.length!==2)throw new Error("Two legal original market positions required");
  return JSON.stringify(planned);
})()'''


def run_advanced(gui, save):
    result = dict(passed=False, assertions={})
    result['setup'] = json.loads(gui(ADVANCED_BOOT))
    state = checkpoint(gui, 210000)
    save('research-village-buildings', 210000, state)
    assert state['players'][1]['hasSharedLos'], 'Original shared LOS research did not apply'
    assert state['players'][1]['classCounts']['Village'] >= 5, 'Original town phase building requirements not satisfied'
    result['assertions']['research'] = True
    gui('Engine.PostNetworkCommand({type:"research",entity:phase4Systems.cc.id,template:"phase_town_athen",metadata:null}); "queued"')
    state = checkpoint(gui, 260000)
    save('town-phase', 260000, state)
    assert state['players'][1]['phase'] == 'town', 'Original town research did not complete'
    result['assertions']['townPhase'] = True
    # Construction pays when the command is processed. Wait for original
    # gathering to fund both 300-wood markets before submitting either order.
    state = checkpoint(gui, 500000)
    save('market-resources', 500000, state)
    assert state['players'][1]['resourceCounts']['wood'] >= 600, 'Original gathering did not fund both markets'
    result['marketPositions'] = json.loads(gui(MARKETS))
    state = checkpoint(gui, 660000)
    save('markets', 660000, state)
    markets = json.loads(gui('JSON.stringify(Engine.GuiInterfaceCall("GetPlayerEntities",{}).map(id=>Engine.GuiInterfaceCall("GetEntityState",id)).filter(entity=>entity.template==="structures/athen/market" && !entity.foundation))'))
    assert len(markets) == 2, 'Original markets did not finish construction'
    market = markets[0]
    trader_template = next(template for template in market['trainer']['entities'] if template.endswith('/support_trader'))
    gui('Engine.PostNetworkCommand(' + json.dumps(dict(type='train',entities=[market['id']],template=trader_template,count=1,metadata=None)) + '); "queued"')
    state = checkpoint(gui, 690000)
    save('trader-production', 690000, state)
    traders = json.loads(gui('JSON.stringify(Engine.GuiInterfaceCall("GetPlayerEntities",{}).map(id=>Engine.GuiInterfaceCall("GetEntityState",id)).filter(entity=>!!entity.trader))'))
    assert traders, 'Original trader was not trained'
    trader = traders[0]
    command = dict(type='setup-trade-route',entities=[trader['id']],source=markets[0]['id'],target=markets[1]['id'],route=[],queued=False)
    gui('Engine.PostNetworkCommand(' + json.dumps(command) + '); "queued"')
    result['tradeCommand'] = command
    state = checkpoint(gui, 780000)
    save('trade-income', 780000, state)
    extended = json.loads(gui('JSON.stringify(Engine.GuiInterfaceCall("GetExtendedSimulationState",{}))'))
    income = extended['players'][1]['sequences']['tradeIncome'][-1]
    assert income > 0, 'Original trader did not deliver trade income'
    result['tradeIncome'] = income
    result['assertions']['trade'] = True
    result['passed'] = True
    return result
