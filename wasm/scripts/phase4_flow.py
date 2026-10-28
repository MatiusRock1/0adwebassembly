"""Original GUI flow shared by native and browser integration tests."""
import json
import time


def wait_gui(gui, expression, timeout=120):
    deadline = time.monotonic() + timeout
    progress_at=time.monotonic()+30
    while time.monotonic() < deadline:
        if gui('String(' + expression + ')') == 'true':
            return
        if time.monotonic()>=progress_at:
            details=gui('''JSON.stringify({loading:typeof g_LoadingPage,selection:typeof g_Selection,
              progress:typeof g_LoadingPage!=="undefined"?g_LoadingPage?.progressBar?.progressbar?.progress:null,
              pauseOnFocusLoss:Engine.ConfigDB_GetValue("user","pauseonfocusloss"),
              globals:Object.keys(globalThis).filter(key=>key.startsWith("g_")).slice(-80),
              captions:Object.fromEntries(["message","title","mbText","mbMessage","mbTitleBar","text","loadingMapName","progressText"].map(name=>[name,Engine.TryGetGUIObjectByName(name)?.caption]))})''')
            print('GUI_WAIT_PROGRESS',expression,details,flush=True)
            dialog=json.loads(details).get('captions',{})
            if 'g_Selection' in expression and dialog.get('mbTitleBar'):
                raise RuntimeError('Unexpected original GUI dialog before session: '+json.dumps(dialog))
            progress_at=time.monotonic()+30
        time.sleep(0.05)
    raise TimeoutError(expression)


def open_original_match(gui, settings, expected_attributes=None):
    # Native main polls before its first Frame, while browser polling starts
    # after a rendered frame. Allow the original startup modal to open first.
    time.sleep(1)
    wait_gui(gui, '''(()=>{
      const welcome=Engine.TryGetGUIObjectByName("btnOK");
      if(welcome){welcome.onPress();return false;}
      const buttons=Engine.TryGetGUIObjectByName("mainMenuButtons");
      if(!buttons)return false;
      buttons.children[2].onPress();return true;
    })()''')
    wait_gui(gui, '''(()=>{
      const welcome=Engine.TryGetGUIObjectByName("btnOK");
      if(welcome){welcome.onPress();return false;}
      const buttons=Engine.TryGetGUIObjectByName("submenuButtons");
      if(!buttons || Engine.GetGUIObjectByName("submenu").hidden)return false;
      buttons.children[0].onPress();return true;
    })()''')
    wait_gui(gui, 'typeof g_GameSettings !== "undefined" && !!g_GameSettings && !!g_SetupWindow')
    gui('g_PlayerAssignments.local.name="Phase4Human"; "ok"')
    if settings.get('mapType')=='scenario':
        # The original default GUI filter excludes demonstration maps. Without
        # selecting All, its map-list watcher substitutes the first legal map
        # while fromInitAttributes is still applying the requested scenario.
        gui('g_SetupWindow.controls.gameSettingsController.guiData.mapFilter.filter="all"; "ok"')
    attributes = json.loads(gui('g_SetupWindow.controls.gameSettingsController.parseSettings(' +
                               json.dumps(settings) + ',false); JSON.stringify(g_GameSettings.toInitAttributes())'))
    assert attributes['map']==settings['map'],('Original GUI substituted the requested map',attributes['map'],settings['map'])
    if expected_attributes is not None:
        assert attributes==expected_attributes,('Original match attributes differ before launch',attributes,expected_attributes)
    gui('g_SetupWindow.controls.gameSettingsController.launchGame(); "ok"')
    wait_gui(gui, 'typeof g_Selection !== "undefined" && !!g_Selection', timeout=300)
    return attributes


def checkpoint(gui, simulation_ms):
    """Pause at an exact original simulation time, or fail on overshoot."""
    current = json.loads(gui('JSON.stringify({time:Engine.GuiInterfaceCall("GetSimulationState",{}).timeElapsed,rate:Engine.GetSimRate()})'))
    gui('Engine.SetPaused(false,false); "ok"')
    expression = '''(()=>{
      const state=Engine.GuiInterfaceCall("GetSimulationState",{});
      if(state.timeElapsed < TARGET) return "waiting";
      Engine.SetPaused(true,false);
      return JSON.stringify(state);
    })()'''.replace('TARGET', str(simulation_ms))
    # Functional parity is checked at exact simulation times, not at a target
    # FPS. Permit slow diagnostic builds while bounding actual lack of progress.
    deadline = time.monotonic() + max(120, 3 * (simulation_ms - current['time']) / (1000 * current['rate']) + 60)
    progress_at = time.monotonic() + 30
    last_progress=current['time'];stagnant_samples=0
    while time.monotonic() < deadline:
        result = gui(expression)
        if result != 'waiting':
            state = json.loads(result)
            if state['timeElapsed'] != simulation_ms:
                raise RuntimeError(f'Checkpoint overshoot: {state["timeElapsed"]} != {simulation_ms}')
            gui('Engine.DumpSimState(); "dumped"')
            return state
        if time.monotonic() >= progress_at:
            progress = gui('JSON.stringify({time:Engine.GuiInterfaceCall("GetSimulationState",{}).timeElapsed,paused:Engine.IsPaused(),rate:Engine.GetSimRate()})')
            print('CHECKPOINT_PROGRESS', simulation_ms, progress, flush=True)
            observed=json.loads(progress)['time']
            stagnant_samples=stagnant_samples+1 if observed==last_progress else 0
            last_progress=observed
            if stagnant_samples>=4:
                detail=gui.checkpoint_diagnostics() if hasattr(gui,'checkpoint_diagnostics') else progress
                raise TimeoutError('No simulation progress for 120 seconds: '+str(detail))
            if hasattr(gui,'checkpoint_diagnostics'):
                print('CHECKPOINT_ENVIRONMENT',json.dumps(gui.checkpoint_diagnostics()),flush=True)
            progress_at = time.monotonic() + 30
        time.sleep(0.005)
    detail=gui.checkpoint_diagnostics() if hasattr(gui,'checkpoint_diagnostics') else None
    raise TimeoutError('Simulation checkpoint'+(' '+json.dumps(detail) if detail else ''))


def parity_settings():
    return dict(mapType='random', map='maps/random/mainland', settings=dict(
        Size=128, Biome='generic/temperate', PlayerPlacement='circle', Seed=12345,
        AISeed=54321, PopulationCap=200, PopulationCapType='player', StartingResources=1000,
        CheatsEnabled=False, RevealMap=False, ExploreMap=False,
        VictoryConditions=['conquest'], PlayerData=[dict(Civ='athen', Name='Phase4Human',AI=False,Team=-1,Color=dict(r=10,g=10,b=190)),
        dict(Civ='mace', Name='Phase4Petra', AI='petra', AIDiff=3, AIBehavior='balanced',Team=-1,Color=dict(r=230,g=10,b=10))]))
