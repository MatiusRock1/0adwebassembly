"""Private Wasm-only relocation of periodic EnsurePlay to the existing worker."""


def adapt(source):
    replacements = [
        ('#include "SoundManager.h"\n', '#include "SoundManager.h"\n\n#if defined(__EMSCRIPTEN__)\n#include "application-audio-ensure.h"\n#endif\n'),
        ('\t\t\tm_Shutdown = true;\n', '\t\t\tm_Shutdown = true;\n#if defined(__EMSCRIPTEN__)\n\t\t\tm_EnsureQueue.Close();\n#endif\n'),
        ('\t\tm_Items->push_back(anItem);\n', '\t\tm_Items->push_back(anItem);\n#if defined(__EMSCRIPTEN__)\n\t\tm_EnsureQueue.Track(anItem);\n#endif\n'),
        ('\n\tvoid CleanupItems()\n', '\n#if defined(__EMSCRIPTEN__)\n\tvoid RequestEnsurePlay(ISoundItem* item)\n\t{\n\t\tm_EnsureQueue.Request(item);\n\t}\n#endif\n\n\tvoid CleanupItems()\n'),
        ('\tvoid Run()\n\t{\n\t\twhile (true)', '\tvoid Run()\n\t{\n#if defined(__EMSCRIPTEN__)\n\t\tusing EnsureClock = WasmApplication::AudioEnsureQueue<ISoundItem>::Clock;\n\t\tauto nextMaintenance = EnsureClock::now();\n#endif\n\t\twhile (true)'),
        ('\t\t\tint pauseTime = 500;\n', '''#if defined(__EMSCRIPTEN__)
            // Wait without the ownership mutex. Fast checks do not run the
            // streaming/fade maintenance more often than its original cadence.
            auto checks = m_EnsureQueue.WaitUntil(nextMaintenance);
            {
                std::lock_guard<std::mutex> workerLock(m_WorkerMutex);
                if (m_Shutdown)
                    return;
                for (const auto& check : checks)
                    if (m_EnsureQueue.IsCurrent(check))
                        check.item->EnsurePlay();
            }
            if (EnsureClock::now() < nextMaintenance)
                continue;
#endif
\t\t\tint pauseTime = 500;
'''),
        ('\t\t\t\t\tm_DeadItems->push_back(*lstr);\n', '\t\t\t\t\t#if defined(__EMSCRIPTEN__)\n\t\t\t\t\tm_EnsureQueue.Forget(*lstr);\n\t\t\t\t\t#endif\n\t\t\t\t\tm_DeadItems->push_back(*lstr);\n'),
        ('\t\t\tSDL_Delay(pauseTime);\n', '#if defined(__EMSCRIPTEN__)\n\t\t\tnextMaintenance = EnsureClock::now() + std::chrono::milliseconds(pauseTime);\n#else\n\t\t\tSDL_Delay(pauseTime);\n#endif\n'),
        ('\tstd::thread m_WorkerThread;\n', '\tstd::thread m_WorkerThread;\n#if defined(__EMSCRIPTEN__)\n\tWasmApplication::AudioEnsureQueue<ISoundItem> m_EnsureQueue;\n#endif\n'),
        ('\t\t\tm_CurrentTune->EnsurePlay();\n', '#if defined(__EMSCRIPTEN__)\n\t\t\tif (m_Worker)\n\t\t\t\tm_Worker->RequestEnsurePlay(m_CurrentTune);\n\t\t\telse\n#endif\n\t\t\tm_CurrentTune->EnsurePlay();\n'),
        ('\t\tif (m_CurrentEnvirons)\n\t\t\tm_CurrentEnvirons->EnsurePlay();\n', '''\t\tif (m_CurrentEnvirons)
        {
#if defined(__EMSCRIPTEN__)
            if (m_Worker)
                m_Worker->RequestEnsurePlay(m_CurrentEnvirons);
            else
#endif
                m_CurrentEnvirons->EnsurePlay();
        }
'''),
    ]
    for before, after in replacements:
        assert source.count(before) == 1, ('Unexpected pinned audio source', before[:100])
        source = source.replace(before, after, 1)
    return source


def adapt_base(source):
    # EnsurePlay now runs concurrently with game-thread Play/Pause/Stop.
    # Keep their flag check and source operation under the same item mutex;
    # calling IsPlaying()/Play() here would recursively acquire that mutex.
    start = source.index('void CSoundBase::EnsurePlay()\n')
    end = source.index('void CSoundBase::SetCone(', start)
    assert source[start:end] == '''void CSoundBase::EnsurePlay()
{
\tif (m_ShouldBePlaying && !m_IsPaused && !IsPlaying())
\t\tPlay();
}

'''
    source = source[:start] + '''void CSoundBase::EnsurePlay()
{
    std::lock_guard<std::mutex> lock(m_ItemMutex);
    if (!m_ShouldBePlaying || m_IsPaused)
        return;
    if (m_ALSource)
    {
        int state;
        alGetSourcei(m_ALSource, AL_SOURCE_STATE, &state);
        AL_CHECK;
        if (state == AL_PLAYING)
            return;
    }
    AL_CHECK;
    if (!m_ALSource)
        return;
    alSourcePlay(m_ALSource);
    ALenum err = alGetError();
    if (err != AL_NO_ERROR)
    {
        if (err == AL_INVALID)
            ((CSoundManager*)g_SoundManager)->SetDistressThroughError();
        else
            ((CSoundManager*)g_SoundManager)->al_ReportError(err, __func__, __LINE__);
    }
}

''' + source[end:]
    start = source.index('void CSoundBase::Stop()\n')
    end = source.index('const Path CSoundBase::GetName()', start)
    block = source[start:end]
    inner = '\t\tstd::lock_guard<std::mutex> lock(m_ItemMutex);\n\n'
    assert block.count(inner) == 1
    block = block.replace(inner, '', 1).replace('{\n', '{\n\tstd::lock_guard<std::mutex> lock(m_ItemMutex);\n', 1)
    source = source[:start] + block + source[end:]
    pause = 'void CSoundBase::Pause()\n{\n'
    assert source.count(pause) == 1
    return source.replace(pause, pause + '\tstd::lock_guard<std::mutex> lock(m_ItemMutex);\n', 1)
