"""Original audio controls after CPU sampling, never inside an FPS capture."""
import json
from zipfile import ZipFile


def verify_worker_audio(page, gui, package):
    state = lambda: page.evaluate('application.getOriginalAudioState()')
    wait_playing = lambda count: page.wait_for_function(
        'n=>application.getOriginalAudioState().contexts.some(c=>c.state==="running" && c.playingSources===n)',
        arg=count, timeout=30000)
    wait_playing(2)
    result = dict(scope='Real original engine commands and SDK playback metadata; not a subjective listening check', before=state())
    assert any(buffer['nonzeroSamples'] for buffer in result['before']['decodedBuffers'])
    # The original pause command pauses ambient/action sounds but keeps music.
    gui('Engine.SetPaused(true,false); "paused"')
    wait_playing(1)
    page.wait_for_timeout(1500)
    result['paused'] = state()
    assert result['paused']['contexts'][0]['playingSources'] == 1
    gui('Engine.SetPaused(false,false); "resumed"')
    wait_playing(2)
    result['resumed'] = state()
    gui('Engine.StopMusic(); "stopped music"')
    wait_playing(1)
    page.wait_for_timeout(1500)
    result['musicStopped'] = state()
    assert result['musicStopped']['contexts'][0]['playingSources'] == 1
    # The GUI file-list API restricts directories. Select a name from the actual
    # immutable archive, then play it through the original engine's VFS.
    with ZipFile(package/'public.zip') as archive:
        track = next(name for name in archive.namelist() if name.startswith('audio/music/') and name.endswith('.ogg'))
    gui('Engine.StartMusic(); Engine.PlayMusic('+json.dumps(track)+',true); "playing original music"')
    wait_playing(2)
    result.update(restarted=state(), originalTrack=track, passed=True)
    return result
