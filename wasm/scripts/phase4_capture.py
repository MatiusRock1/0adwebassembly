"""Verify ownership changes by original capture combat, with cheats disabled."""
import json
import time
from phase4_flow import checkpoint

def capture_settings():
    return dict(mapType='scenario',map='maps/scenarios/demo_trading',settings=dict(
        Seed=12345,AISeed=54321,StartingResources=10000,CheatsEnabled=False,
        PopulationCap=200,PopulationCapType='player',
        RevealMap=True,VictoryConditions=[],PlayerData=[
            dict(Civ='rome',Name='Phase4Human',AI=False,Team=0,Color=dict(r=46,g=46,b=200)),
            dict(Civ='achae',Name='Phase4Opponent',AI=False,Team=0,Color=dict(r=150,g=20,b=20)),
            dict(Civ='cart',Name='Phase4Third',AI=False,Team=0,Color=dict(r=255,g=255,b=0))]))

def run_capture(gui,save):
    result=dict(passed=False,commands=[])
    state=checkpoint(gui,10000);save('capture-initial',10000,state)
    # demo_trading starts its factions on the same team. A legal original
    # diplomacy command must make the target hostile before capture combat;
    # attacking an allied market correctly leaves ownership unchanged.
    diplomacy=dict(type='diplomacy',player=2,to='enemy')
    gui('Engine.PostNetworkCommand('+json.dumps(diplomacy)+'); "queued"')
    result['commands'].append(diplomacy)
    # Coordinates come from the pinned, unmodified demo_trading.xml market.
    gui('Engine.CameraMoveTo(775.5876,506.4651); "camera"')
    time.sleep(2)
    result['setup']=json.loads(gui('''(()=>{
      const target=Engine.PickPlayerEntitiesOnScreen(2).map(id=>Engine.GuiInterfaceCall("GetEntityState",id)).find(entity=>entity.template.endsWith("/market"));
      if(!target)throw new Error("Original opposing market not visible");
      const centres=Engine.GuiInterfaceCall("GetPlayerEntities",{}).map(id=>Engine.GuiInterfaceCall("GetEntityState",id)).filter(entity=>entity.template.endsWith("/civil_centre"));
      centres.sort((a,b)=>(a.position.x-target.position.x)**2+(a.position.z-target.position.z)**2-((b.position.x-target.position.x)**2+(b.position.z-target.position.z)**2));
      const centre=centres[0];
      const template=centre.trainer.entities.find(template=>/infantry_(swordsman|spearman|pikeman)_b$/.test(template));
      if(!template)throw new Error("Original civic centre has no capture infantry");
      globalThis.phase4Capture={target:target.id,template};
      const command={type:"train",entities:[centre.id],template,count:30,metadata:null};
      Engine.PostNetworkCommand(command);
      return JSON.stringify({target,centre:centre.id,template,command});
    })()'''))
    result['commands'].append(result['setup']['command'])
    state=checkpoint(gui,200000);save('capture-infantry-production',200000,state)
    assert state['players'][1]['isEnemy'][2] and not state['players'][1]['isAlly'][2], 'Original diplomacy did not make the capture target hostile'
    attack=json.loads(gui('''(()=>{
      const infantry=Engine.GuiInterfaceCall("GetPlayerEntities",{}).map(id=>Engine.GuiInterfaceCall("GetEntityState",id)).filter(entity=>entity.attack?.Capture);
      if(infantry.length<20)throw new Error("Original production did not train the required capture infantry");
      const command={type:"attack",entities:infantry.map(entity=>entity.id),target:phase4Capture.target,queued:false,allowCapture:true};
      Engine.PostNetworkCommand(command);return JSON.stringify(command);
    })()'''))
    result['commands'].append(attack)
    state=checkpoint(gui,400000);save('original-ownership-capture',400000,state)
    result['capturedMarket']=json.loads(gui('JSON.stringify(Engine.GuiInterfaceCall("GetEntityState",phase4Capture.target))'))
    assert result['capturedMarket']['player']==1,'Original capture did not transfer market ownership'
    assert result['capturedMarket']['capturePoints'][1]>0
    result['passed']=True
    return result
