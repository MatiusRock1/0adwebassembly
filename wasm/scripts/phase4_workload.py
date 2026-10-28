"""Prepare load through original commands, retaining original AI and combat."""
import json
from pathlib import Path
import time

MANIFEST_PATH = Path(__file__).resolve().parents[1] / 'scenario/phase4-workloads.json'
MANIFEST = json.loads(MANIFEST_PATH.read_text())

OBSERVE = r'''(()=>{
  const observations=[];
  for(const player of [1,2]){
    Engine.SetViewedPlayer(player);
    const entities=Engine.GuiInterfaceCall("GetPlayerEntities",{}).map(id=>Engine.GuiInterfaceCall("GetEntityState",id));
    observations.push({player,cc:entities.find(entity=>entity.template.endsWith("/civil_centre")),
      units:entities.filter(entity=>!!entity.unitAI).map(entity=>({id:entity.id,position:entity.position,hitpoints:entity.hitpoints,state:entity.unitAI.state}))});
  }
  Engine.SetViewedPlayer(1);
  return JSON.stringify({players:observations,simulation:Engine.GuiInterfaceCall("GetSimulationState",{}),pendingTurns:Engine.GetPendingTurns(),rate:Engine.GetSimRate(),paused:Engine.IsPaused()});
})()'''


def observe(gui):
    return json.loads(gui(OBSERVE))


# Measurement-window samples. The full OBSERVE asks GetEntityState for every
# entity on the renderer thread (90-190 ms in combat), which itself stalls frames.
# classCounts.Unit is maintained incrementally by the original TechnologyManager;
# populate(initial=True) checks it equals the UnitAI count of the full OBSERVE.
OBSERVE_COUNTS = r'''(()=>{
  const state=Engine.GuiInterfaceCall("GetSimulationState",{});
  return JSON.stringify({players:[1,2].map(player=>({player,units:(state.players[player].classCounts||{}).Unit||0})),
    simulation:{timeElapsed:state.timeElapsed},pendingTurns:Engine.GetPendingTurns(),rate:Engine.GetSimRate(),paused:Engine.IsPaused()});
})()'''

# Entity ids only; the viewed player is restored within the same evaluation,
# so no frame is rendered from player 2's perspective.
PLAYER_ENTITY_IDS = r'''(()=>{
  const ids={};
  for(const player of [1,2]){Engine.SetViewedPlayer(player);ids[player]=Engine.GuiInterfaceCall("GetPlayerEntities",{});}
  Engine.SetViewedPlayer(1);
  return JSON.stringify(ids);
})()'''


def observe_counts(gui):
    state = json.loads(gui(OBSERVE_COUNTS))
    for player in state['players']:
        player['liveUnits'] = player['units']
    return state


def live_units(state):
    """Live unit total from either a full or a count-only observation."""
    return sum(len(p['units']) if isinstance(p['units'], list) else p['units'] for p in state['players'])


# Ids already ordered by the harness, per player; reset by populate(initial=True).
_ordered = {}


def graphics_settings(gui):
    return json.loads(gui('''JSON.stringify(Object.fromEntries([
      "vsync","adaptivefps.session","shadows","shadowpcf","postproc",
      "particles","gpuskinning","silhouettes","watereffects","waterfancyeffects",
      "waterrealdepth","waterreflection","waterrefraction","textures.quality",
      "shadowquality","textures.maxanisotropy","antialiasing","renderactors",
      "max_actor_quality","materialmgr.quality","shadowscascadecount",
      "shadowscascadedistanceratio","shadowscutoffdistance","shadowscovermap"
    ].map(key=>[key,Engine.ConfigDB_GetValue("user",key)])))'''))


def apply_graphics_profile(gui, profile):
    """Apply declared original options temporarily, without saving user prefs."""
    gui('''(()=>{for(const [key,value] of Object.entries(PROFILE))
      Engine.ConfigDB_CreateValue("user",key,value);return "matched graphics profile";})()'''.replace('PROFILE',json.dumps(profile)))
    actual=graphics_settings(gui)
    if actual!=profile:raise RuntimeError('Original graphics profile did not apply: '+json.dumps(actual))
    return actual


def populate(gui, wait, workload, initial=True):
    if not initial:
        return replenish(gui, wait, workload)
    trace = []
    for _ in range(12):
        state = observe(gui)
        if all(len(player['units']) >= MANIFEST['targetUnitsPerPlayer'] for player in state['players']):
            break
        for player in state['players']:
            if len(player['units']) >= MANIFEST['targetUnitsPerPlayer']:
                continue
            if not player['cc']:
                raise RuntimeError('Original civic centre lost; cannot preserve workload')
            command = dict(type='cheat',player=player['player'],action='createunits',parameter=200,
                selected=[player['cc']['id']],templates=[MANIFEST['preparationTemplates'][player['player']-1]])
            gui('Engine.SetPlayerID(' + str(player['player']) + '); Engine.PostNetworkCommand(' + json.dumps(command) + '); Engine.SetPlayerID(1); "queued"')
            trace.append(dict(player=player['player'], command=command))
        wait(1000)
    state = observe(gui)
    if sum(len(player['units']) for player in state['players']) < MANIFEST['minimumLiveUnits']:
        raise RuntimeError('Required original unit workload not reached')
    if workload == 'combat':
        centres = [player['cc']['position'] for player in state['players']]
        target = dict(x=sum(position['x'] for position in centres)/2,
                      z=sum(position['z'] for position in centres)/2)
    else:
        target = state['players'][0]['cc']['position']
    gui('Engine.CameraMoveTo(' + str(target['x']) + ',' + str(target['z']) + '); "camera"')
    issue_orders(gui, state, workload, target, trace)
    counts = observe_counts(gui)
    expected = {p['player']: len(p['units']) for p in state['players']}
    if {p['player']: p['units'] for p in counts['players']} != expected:
        raise RuntimeError('classCounts.Unit differs from the UnitAI count: ' + json.dumps([expected, counts['players']]))
    ids = json.loads(gui(PLAYER_ENTITY_IDS))
    _ordered.clear()
    _ordered.update(target=target, cc={p['player']: p['cc']['id'] for p in state['players']},
                    **{str(player): set(ids[str(player)]) for player in (1, 2)})
    return dict(state=state, target=target, trace=trace, countCheck=dict(unitAI=expected, classCounts=counts['players']))


def replenish(gui, wait, workload):
    """Top each army up to replenishToUnitsPerPlayer and order only the new units.

    Units already in the fight keep their original order; new units receive the
    same original attack-walk/patrol command as the initial army.
    """
    trace = []
    state = observe_counts(gui)
    target = _ordered['target']
    goal = MANIFEST['replenishToUnitsPerPlayer']
    ids_now = json.loads(gui(PLAYER_ENTITY_IDS))
    created = False
    for player in state['players']:
        missing = goal - player['units']
        if missing <= 0:
            continue
        cc = _ordered['cc'][player['player']]
        if cc not in ids_now[str(player['player'])]:
            raise RuntimeError('Original civic centre lost; cannot preserve workload')
        command = dict(type='cheat', player=player['player'], action='createunits', parameter=missing,
            selected=[cc], templates=[MANIFEST['preparationTemplates'][player['player']-1]])
        gui('Engine.SetPlayerID(' + str(player['player']) + '); Engine.PostNetworkCommand(' + json.dumps(command) + '); Engine.SetPlayerID(1); "queued"')
        trace.append(dict(player=player['player'], command=command))
        created = True
    if created:
        # The cheat runs in a later turn; then order only the entities it added.
        wait(1000)
        ids_now = json.loads(gui(PLAYER_ENTITY_IDS))
    for player in (1, 2):
        current = set(ids_now[str(player)])
        new = sorted(current - _ordered[str(player)])
        _ordered[str(player)] = current
        if not new or (workload == 'skirmish' and player == 2):
            continue
        command = dict(type='attack-walk' if workload == 'combat' else 'patrol', entities=new,
            x=target['x'] + (-12 if player == 1 else 12), z=target['z'] + (0 if workload == 'combat' else 40),
            queued=False, allowCapture=False)
        gui('Engine.SetPlayerID(' + str(player) + '); Engine.PostNetworkCommand(' + json.dumps(command) + '); Engine.SetPlayerID(1); "queued"')
        trace.append(dict(player=player, command=command))
    return dict(state=state, target=target, trace=trace)


def issue_orders(gui, state, workload, target, trace):
    for player in state['players']:
        if workload == 'skirmish' and player['player'] == 2:
            continue
        command = dict(type='attack-walk' if workload == 'combat' else 'patrol',
            entities=[unit['id'] for unit in player['units']],
            x=target['x'] + (-12 if player['player'] == 1 else 12), z=target['z'] + (0 if workload == 'combat' else 40),
            queued=False, allowCapture=False)
        gui('Engine.SetPlayerID(' + str(player['player']) + '); Engine.PostNetworkCommand(' + json.dumps(command) + '); Engine.SetPlayerID(1); "queued"')
        trace.append(dict(player=player['player'], command=command))
