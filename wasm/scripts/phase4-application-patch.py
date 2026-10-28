"""Apply explicit browser entry changes to an isolated cached source copy."""
import argparse
import difflib
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--patch', type=Path, required=True)
    args = parser.parse_args()
    changes = []

    def edit(relative, old, new, expected=1):
        path = args.source / relative
        before = path.read_text()
        # Later metric extensions retain the observer but change its argument
        # list. Bootstrap it only once; subsequent edits migrate each field.
        if relative == 'main.cpp' and old == '\tg_Renderer.RenderFrame(true);' and 'static unsigned browserFrame = 0;' in before:
            return
        if relative == 'main.cpp' and old == '\tg_Renderer.RenderFrame(true);\n\tstatic unsigned browserFrame = 0;' and 'WasmApplication::RunDeferredAudioIdle(); // fallback when rendering is skipped' in before:
            return
        if relative == 'main.cpp' and old == '\t\tg_Game && g_Game->m_Paused);' and 'phase4UpdateMilliseconds, realTimeSinceLastFrame * 1000);' in before:
            return
        if relative == 'renderer/backend/gl/ShaderProgram.cpp' and old == '\t\t\tout = includeFile.GetAsString();' and 'float phase4BilinearShadow' in before:
            return
        if new in before:
            return
        if before.count(old) != expected:
            raise RuntimeError('Unexpected source for ' + relative)
        after = before.replace(old, new)
        path.write_text(after)
        changes.extend(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                          fromfile='a/source/' + relative,
                                          tofile='b/source/' + relative))

    edit('main.cpp', '#include "lib/precompiled.h"',
         '#include "lib/precompiled.h"\n#include "application-clock.h"')
    edit('main.cpp', '#include "application-clock.h"',
         '#include "application-clock.h"\n#include "application-deferred-audio.h"')
    edit('main.cpp', '#include "application-deferred-audio.h"',
         '#include "application-deferred-audio.h"\n#include "application-deferred-replay.h"')
    edit('ps/Replay.cpp', '#include "Replay.h"',
         '#include "Replay.h"\n#include "application-deferred-replay.h"')
    edit('ps/Replay.cpp', 'CReplayLogger::~CReplayLogger()\n{\n\tdelete m_Stream;',
         'CReplayLogger::~CReplayLogger()\n{\n'
         '\tif (m_Stream) WasmApplication::replayFlushes.DrainStream(*m_Stream);\n\tdelete m_Stream;')
    edit('ps/Replay.cpp', '\tm_Stream->flush();',
         '\tWasmApplication::replayFlushes.Schedule(*m_Stream);')
    edit('ps/Replay.cpp', 'void CReplayLogger::SaveMetadata(const CSimulation2& simulation)\n{',
         'void CReplayLogger::SaveMetadata(const CSimulation2& simulation)\n{\n'
         '\tif (m_Stream) WasmApplication::replayFlushes.DrainStream(*m_Stream);')
    edit('main.cpp', '#if OS_UNIX\n\t// Don\'t allow people to run the game with root permissions,',
         '#if OS_UNIX && !defined(__EMSCRIPTEN__)\n'
         '\t// Browser virtual UID does not grant host root permissions.\n'
         '\t// Don\'t allow people to run the game with root permissions,')
    # Keep the original loop and all RAII owners; the browser's display clock
    # wakes the engine pthread. No detached stack or manual simulation loop.
    edit('main.cpp', '\t\t\t\twhile (g_Shutdown == ShutdownType::None)',
         '\t\t\t\tWasmApplication::DisplayClock browserClock;\n'
         '\t\t\t\twhile (g_Shutdown == ShutdownType::None)')
    edit('main.cpp', '\t\t\t\t\tif (isVisual)\n\t\t\t\t\t{',
         '\t\t\t\t\tif (isVisual)\n\t\t\t\t\t{\n'
         '\t\t\t\t\t\tbrowserClock.Wait();\n'
         '\t\t\t\t\t\tWasmApplication::ProcessTestRequest();')
    edit('ps/TaskManager.cpp', 'size_t GetDefaultNumberOfWorkers()\n{',
         'size_t GetDefaultNumberOfWorkers()\n{\n'
         '#if defined(__EMSCRIPTEN__)\n'
         '\treturn MIN_WORKERS; // bounded browser worker pool\n#endif')
    edit('main.cpp', '\tg_Renderer.RenderFrame(true);',
         '\tg_Renderer.RenderFrame(true);\n'
         '\tstatic unsigned browserFrame = 0;\n'
         '\tMAIN_THREAD_EM_ASM({\n'
         '\t\tconst sample = ({frame:$0, tick:$1, gameStarted:Boolean($2), width:$3, height:$4, paused:Boolean($5), wasmHeapBytes:HEAPU8.length, receivedMs:performance.now()});\n'
         '\t\tModule.applicationState = sample;\n'
         '\t\t(Module.applicationFrames ||= []).push(sample);\n'
         '\t\tif (Module.applicationFrames.length > 65000) Module.applicationFrames.shift();\n'
         '\t}, ++browserFrame, g_Game && g_Game->GetTurnManager() ? g_Game->GetTurnManager()->GetCurrentTurn() : 0,\n'
         '\t\tg_Game && g_Game->IsGameStarted(), g_VideoMode.GetWindowWidth(), g_VideoMode.GetWindowHeight(),\n'
         '\t\tg_Game && g_Game->m_Paused);')
    # Observation must follow the queued presentation without forcing the
    # renderer thread to wait for its own diagnostic sample every frame.
    edit('main.cpp', '\tstatic unsigned browserFrame = 0;\n\tMAIN_THREAD_EM_ASM({',
         '\tstatic unsigned browserFrame = 0;\n\tMAIN_THREAD_ASYNC_EM_ASM({')
    edit('main.cpp', '\tif (g_SoundManager)\n\t\tg_SoundManager->IdleTask();',
         '\tif (g_SoundManager)\n'
         '\t\tWasmApplication::ScheduleAudioIdle([] { if (g_SoundManager) g_SoundManager->IdleTask(); });')
    edit('main.cpp', '\tg_Renderer.RenderFrame(true);\n\tstatic unsigned browserFrame = 0;',
         '\tg_Renderer.RenderFrame(true);\n'
         '\tWasmApplication::RunDeferredAudioIdle(); // fallback when rendering is skipped\n'
         '\tstatic unsigned browserFrame = 0;')
    edit('main.cpp', '\tWasmApplication::RunDeferredAudioIdle(); // fallback when rendering is skipped',
         '\tWasmApplication::replayFlushes.Drain(); // fallback when rendering is skipped\n'
         '\tWasmApplication::RunDeferredAudioIdle(); // fallback when rendering is skipped')
    edit('main.cpp', '\tif (g_Game && g_Game->IsGameStarted() && needUpdate)\n\t{',
         '\tdouble phase4UpdateMilliseconds = 0;\n'
         '\tif (g_Game && g_Game->IsGameStarted() && needUpdate)\n\t{')
    edit('main.cpp', '\t\tif (!rlInterface)\n\t\t\tg_Game->Update(realTimeSinceLastFrame);',
         '\t\tif (!rlInterface)\n\t\t{\n'
         '\t\t\tconst double phase4UpdateStart = timer_Time();\n'
         '\t\t\tg_Game->Update(realTimeSinceLastFrame);\n'
         '\t\t\tphase4UpdateMilliseconds = (timer_Time() - phase4UpdateStart) * 1000;\n\t\t}')
    edit('main.cpp', '\t\tModule.applicationState = sample;',
         '\t\tsample.updateMilliseconds = $6;\n\t\tModule.applicationState = sample;')
    edit('main.cpp', '\t\tg_Game && g_Game->m_Paused);',
         '\t\tg_Game && g_Game->m_Paused, phase4UpdateMilliseconds);')
    edit('main.cpp', '\tconst float realTimeSinceLastFrame{static_cast<float>(\n\t\t1.0 / (fixedFrameFrequency > 0 ? fixedFrameFrequency : g_frequencyFilter->SmoothedFrequency()))};',
         '\tconst float realTimeSinceLastFrame{WasmApplication::frameTime.Advance(time, fixedFrameFrequency)};')
    edit('main.cpp', '\t\t(Module.applicationFrames ||= []).push(sample);',
         '\t\tsample.clockDeltaMilliseconds = $7;\n\t\t(Module.applicationFrames ||= []).push(sample);')
    edit('main.cpp', '\t\tg_Game && g_Game->m_Paused, phase4UpdateMilliseconds);',
         '\t\tg_Game && g_Game->m_Paused, phase4UpdateMilliseconds, realTimeSinceLastFrame * 1000);')
    # Preserve the diagnostic sample's position after its queued presentation.
    # GL continues publishing directly; WebGPU command tasks may yield to RAF.
    edit('main.cpp', '\t\tconst sample = ({frame:$0,',
         '\t\tconst publish = () => {\n\t\tconst sample = ({frame:$0,')
    edit('main.cpp', '\t\tif (Module.applicationFrames.length > 65000) Module.applicationFrames.shift();',
         '\t\tif (Module.applicationFrames.length > 65000) Module.applicationFrames.shift();\n'
         '\t\t};\n'
         '\t\tconst dispatcher = Module.webgpuBackend?.commandDispatcher;\n'
         '\t\tif (dispatcher) dispatcher.enqueue(publish, () => {}, error => { err(String(error)); abort(String(error)); });\n'
         '\t\telse publish();')
    edit('scriptinterface/Context.cpp', '#include "Context.h"',
         '#include "Context.h"\n#include <chrono>\n#include <emscripten.h>')
    edit('scriptinterface/Context.cpp', '\tif (progress == JS::GC_SLICE_BEGIN)',
         '\tstatic thread_local std::chrono::steady_clock::time_point phase4GCStart;\n'
         '\tif (progress == JS::GC_SLICE_BEGIN)\n'
         '\t\tphase4GCStart = std::chrono::steady_clock::now();\n'
         '\telse if (progress == JS::GC_SLICE_END)\n\t{\n'
         '\t\tconst double milliseconds = std::chrono::duration<double, std::milli>(\n'
         '\t\t\tstd::chrono::steady_clock::now() - phase4GCStart).count();\n'
         '\t\tMAIN_THREAD_EM_ASM({\n'
         '\t\t\t(Module.applicationGC ||= []).push({receivedMs:performance.now(),durationMs:$0});\n'
         '\t\t\tif(Module.applicationGC.length>10000)Module.applicationGC.shift();\n'
         '\t\t}, milliseconds);\n\t}\n'
         '\tif (progress == JS::GC_SLICE_BEGIN)')
    # Unavailable platform backends report failure and follow the original
    # Preserve the original four bilinear PCF samples on the ES 1.00 shader
    # path. GLES2 samplers cannot compare depth, so perform the same bilinear
    # comparisons explicitly; never interpolate depth before comparing it.
    shadow_helper = '''
#if USE_SHADOW && USE_SHADOW_PCF && !USE_SHADOW_SAMPLER
float phase4BilinearShadow(vec2 uv, float depth)
{
  vec2 pixel = uv * shadowScale.xy - 0.5;
  vec2 fraction = fract(pixel);
  vec2 base = (floor(pixel) + 0.5) * shadowScale.zw;
  vec2 texel = shadowScale.zw;
  vec4 comparisons = step(vec4(depth), vec4(
    SAMPLE_2D(GET_DRAW_TEXTURE_2D(shadowTex), base).r,
    SAMPLE_2D(GET_DRAW_TEXTURE_2D(shadowTex), base + vec2(texel.x, 0.0)).r,
    SAMPLE_2D(GET_DRAW_TEXTURE_2D(shadowTex), base + vec2(0.0, texel.y)).r,
    SAMPLE_2D(GET_DRAW_TEXTURE_2D(shadowTex), base + texel).r));
  return mix(mix(comparisons.x, comparisons.y, fraction.x),
             mix(comparisons.z, comparisons.w, fraction.x), fraction.y);
}
#endif
'''
    shadow_filter = '''
#if USE_SHADOW_PCF
    vec2 offset = fract(shadowVertex.xy - 0.5);
    vec4 size = vec4(offset + 1.0, 2.0 - offset);
    vec4 weight = (vec4(1.0, 1.0, -0.5, -0.5) + (shadowVertex.xy - 0.5*offset).xyxy) * shadowScale.zwzw;
    return (1.0/9.0)*dot(size.zxzx*size.wwyy, vec4(
      phase4BilinearShadow(weight.zw, biasedShdwZ),
      phase4BilinearShadow(weight.xw, biasedShdwZ),
      phase4BilinearShadow(weight.zy, biasedShdwZ),
      phase4BilinearShadow(weight.xy, biasedShdwZ)));
#else
    return (biasedShdwZ < SAMPLE_2D(GET_DRAW_TEXTURE_2D(shadowTex), shadowVertex.xy).x ? 1.0 : 0.0);
#endif
'''
    edit('renderer/backend/gl/ShaderProgram.cpp',
         '\t\t\tout = includeFile.GetAsString();',
         '\t\t\tout = includeFile.GetAsString();\n'
         '#if defined(__EMSCRIPTEN__)\n'
         '\t\t\tif (includePath == "common/shadows_fragment.h")\n\t\t\t{\n'
         '\t\t\t\tout.Replace("float getShadowImpl(vec4 shadowVertex, float shadowBias)",\n'
         '\t\t\t\t\tR"phase4(' + shadow_helper + 'float getShadowImpl(vec4 shadowVertex, float shadowBias))phase4");\n'
         '\t\t\t\tout.Replace("    return (biasedShdwZ < SAMPLE_2D(GET_DRAW_TEXTURE_2D(shadowTex), shadowVertex.xy).x ? 1.0 : 0.0);",\n'
         '\t\t\t\t\tR"phase4(' + shadow_filter + ')phase4");\n'
         '\t\t\t}\n#endif')
    edit('renderer/backend/gl/ShaderProgram.cpp',
         '    vec2 offset = fract(shadowVertex.xy - 0.5);\n'
         '    vec4 size = vec4(offset + 1.0, 2.0 - offset);\n'
         '    vec4 weight = (vec4(1.0, 1.0, -0.5, -0.5) + (shadowVertex.xy - 0.5*offset).xyxy) * shadowScale.zwzw;',
         '    // The non-shadow-sampler vertex path supplies normalized UVs.\n'
         '    vec2 shadowTexelCoordinates = shadowVertex.xy * shadowScale.xy;\n'
         '    vec2 offset = fract(shadowTexelCoordinates - 0.5);\n'
         '    vec4 size = vec4(offset + 1.0, 2.0 - offset);\n'
         '    vec4 weight = (vec4(1.0, 1.0, -0.5, -0.5) + (shadowTexelCoordinates - 0.5*offset).xyxy) * shadowScale.zwzw;')
    # downgrade path. The actual GL/dummy implementations remain original.
    edit('ps/VideoMode.cpp',
         '\t\tm_BackendDevice = Renderer::Backend::Vulkan::CreateDevice(window);',
         '\t\tLOGERROR("Vulkan is unavailable in this WebGL browser target");\n'
         '\t\tm_BackendDevice.reset();')
    edit('ps/GameSetup/Paths.cpp',
         'OsPath Paths::Root(const OsPath& argv0)\n{\n#if OS_ANDROID',
         'OsPath Paths::Root(const OsPath& argv0)\n{\n#if defined(__EMSCRIPTEN__)\n'
         '\treturn OsPath("/"); // /data is the browser VFS data directory\n#elif OS_ANDROID')
    edit('ps/DllLoader.cpp',
         'static void* LoadAnyVariant(const CStr& name, std::stringstream& errors)\n{',
         'static void* LoadAnyVariant(const CStr& name, std::stringstream& errors)\n{\n'
         '#if defined(__EMSCRIPTEN__)\n'
         '\terrors << "Native shared libraries are unavailable in the browser: " << name;\n'
         '\treturn nullptr;\n#endif')
    edit('ps/VideoMode.cpp', '// Require GLES 2.0\n'
         '\t\t\t\tSDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_ES);\n'
         '\t\t\t\tSDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 2);',
         '// Require GLES 3.0 / WebGL 2 in the browser.\n'
         '\t\t\t\tSDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_ES);\n'
         '\t\t\t\tSDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 3);')
    edit('ps/VideoMode.cpp', 'void CVideoMode::UpdateRenderer(int w, int h)\n{',
         'void CVideoMode::UpdateRenderer(int w, int h)\n{\n'
         '\temscripten_set_canvas_element_size("#canvas", w, h);')
    edit('ps/VideoMode.cpp', '#include "VideoMode.h"',
         '#include "VideoMode.h"\n#include <emscripten/html5.h>')
    edit('renderer/backend/gl/Device.cpp', '#include "Device.h"',
         '#include "Device.h"\n#include <emscripten/html5.h>')
    edit('renderer/backend/gl/Device.cpp',
         '\t\tdevice->m_Context = SDL_GL_CreateContext(device->m_Window);',
         '\t\tEmscriptenWebGLContextAttributes browserAttributes;\n'
         '\t\temscripten_webgl_init_context_attributes(&browserAttributes);\n'
         '\t\tbrowserAttributes.majorVersion = 2;\n'
         '\t\tbrowserAttributes.alpha = false;\n'
         '\t\tbrowserAttributes.antialias = false;\n'
         '\t\tbrowserAttributes.depth = true;\n'
         '\t\tbrowserAttributes.stencil = true;\n'
         '\t\tbrowserAttributes.explicitSwapControl = true;\n'
         '\t\tbrowserAttributes.renderViaOffscreenBackBuffer = true;\n'
         '\t\tbrowserAttributes.proxyContextToMainThread = EMSCRIPTEN_WEBGL_CONTEXT_PROXY_ALWAYS;\n'
         '\t\tconst int browserContext = emscripten_webgl_create_context("#canvas", &browserAttributes);\n'
         '\t\tif (browserContext <= 0 || emscripten_webgl_make_context_current(browserContext) != EMSCRIPTEN_RESULT_SUCCESS)\n'
         '\t\t{\n\t\t\tLOGERROR("Failed to create/make current the browser WebGL context");\n'
         '\t\t\tif (browserContext > 0) emscripten_webgl_destroy_context(browserContext);\n'
         '\t\t\treturn nullptr;\n\t\t}\n'
         '\t\tdevice->m_Context = reinterpret_cast<SDL_GLContext>(static_cast<intptr_t>(browserContext));')
    edit('renderer/backend/gl/Device.cpp', '\t\tSDL_GL_DeleteContext(m_Context);',
         '\t\temscripten_webgl_destroy_context(static_cast<int>(reinterpret_cast<intptr_t>(m_Context)));')
    edit('renderer/backend/gl/SwapChain.cpp', '#include "SwapChain.h"',
         '#include "SwapChain.h"\n#include <emscripten/html5.h>')
    edit('renderer/backend/gl/SwapChain.cpp', '\t\tSDL_GL_SwapWindow(m_Window);',
         '\t\tif (emscripten_webgl_commit_frame() != EMSCRIPTEN_RESULT_SUCCESS)\n'
         '\t\t\tLOGERROR("Browser WebGL presentation failed");')
    edit('renderer/backend/gl/SwapChain.cpp', '\tSDL_GL_SetSwapInterval(vsync ? 1 : 0);',
         '\t(void)vsync; // browser presentation is paced by RAF, not SDL/EGL timing')
    edit('soundmanager/SoundManager.cpp', 'void CSoundManager::RunHardwareDetection()\n{',
         'void CSoundManager::RunHardwareDetection()\n{\n'
         '#if defined(__EMSCRIPTEN__)\n'
         '\t// Web Audio exposes the active virtual device, not host-device enumeration.\n'
         '\tif (const ALCchar* name = alcGetString(m_Device, ALC_DEVICE_SPECIFIER))\n'
         '\t\tm_SoundCardNames = name;\n'
         '\tif (const ALchar* version = alGetString(AL_VERSION))\n'
         '\t\tm_OpenALVersion = version;\n'
         '\treturn;\n#endif')
    edit('ps/VideoMode.cpp', '\t\tcase SDL_WINDOWEVENT_RESIZED:',
         '#if defined(__EMSCRIPTEN__)\n'
         '\t\tcase SDL_WINDOWEVENT_RESIZED:\n'
         '\t\t\tbreak; // CSS dimensions are not framebuffer dimensions.\n'
         '\t\tcase 255: // explicit browser framebuffer resize\n'
         '#else\n\t\tcase SDL_WINDOWEVENT_RESIZED:\n#endif')
    edit('ps/VideoMode.cpp', '\t\tflags |= SDL_WINDOW_SHOWN | SDL_WINDOW_RESIZABLE;',
         '\t\tflags |= SDL_WINDOW_SHOWN;\n'
         '#if !defined(__EMSCRIPTEN__)\n\t\tflags |= SDL_WINDOW_RESIZABLE;\n#endif\n'
         '\t\t// Browser shell owns CSS sizing; SDL must not overwrite the framebuffer.')
    edit('renderer/backend/gl/ShaderProgram.cpp',
         '\tsource = preprocessor.Preprocess(file.GetAsString());',
         '\tCStr shaderText = file.GetAsString();\n'
         '#if defined(__EMSCRIPTEN__)\n'
         '\t// Original parallax iteration count is capped at 20. ES 1.00 requires\n'
         '\t// a constant loop bound; the early break preserves every sample.\n'
         '\tif (path == VfsPath("shaders/glsl/model_common.fs"))\n'
         '\t\tshaderText.Replace("for (int i = 0; i < iter; ++i) {",\n'
         '\t\t\t"for (int i = 0; i < 20; ++i) { if (i >= iter) break;");\n'
         '#endif\n\tsource = preprocessor.Preprocess(shaderText);')
    edit('ps/CLogger.cpp', '\t\ttextRenderer.PrintfAdvance(L"[%8.3f] %hs: ", msg.time, type);',
         '#if defined(__EMSCRIPTEN__)\n'
         '\t\ttextRenderer.PrintfAdvance(L"[%8.3f] %s: ", msg.time, type);\n'
         '#else\n\t\ttextRenderer.PrintfAdvance(L"[%8.3f] %hs: ", msg.time, type);\n#endif')
    edit('soundmanager/SoundManager.cpp', '\tif (m_Context)\n\t\talcDestroyContext(m_Context);',
         '\tif (m_Context)\n\t{\n'
         '#if defined(__EMSCRIPTEN__)\n\t\talcMakeContextCurrent(nullptr);\n#endif\n'
         '\t\talcDestroyContext(m_Context);\n\t}')
    edit('lib/file/vfs/vfs.cpp', '#include <cstdio>', '#include <cstdio>\n#include <cstdlib>')
    edit('lib/file/vfs/vfs.cpp',
         ' std::printf("VFS_READ %s\\n", pathname.string8().c_str());',
         ' if (std::getenv("PHASE4_TRACE_VFS"))\n'
         '  std::printf("VFS_READ %s\\n", pathname.string8().c_str());', expected=2)
    # WebGL cannot retain native client-array pointers into temporary C++ data.
    # Upload each binding separately before recording the original draw call.
    edit('renderer/backend/gl/DeviceCommandContext.h',
         '\tconst void* m_IndexBufferData = nullptr;',
         '\tconst void* m_IndexBufferData = nullptr;\n'
         '\tstd::array<std::unique_ptr<IBuffer>, 16> m_BrowserVertexBuffers;\n'
         '\tstd::unique_ptr<IBuffer> m_BrowserIndexBuffer;')
    edit('renderer/backend/gl/DeviceCommandContext.cpp',
         '\tENSURE(dataSize > 0);\n\tBindBuffer(CBuffer::Type::VERTEX, nullptr);',
         '\tENSURE(dataSize > 0);\n'
         '#if defined(__EMSCRIPTEN__)\n'
         '\tENSURE(bindingSlot < m_BrowserVertexBuffers.size());\n'
         '\tauto& buffer = m_BrowserVertexBuffers[bindingSlot];\n'
         '\tBindBuffer(CBuffer::Type::VERTEX, nullptr);\n'
         '\tif (!buffer || buffer->GetSize() < dataSize)\n'
         '\t\tbuffer = m_Device->CreateBuffer("browser transient vertices", IBuffer::Type::VERTEX, dataSize, IBuffer::Usage::DYNAMIC | IBuffer::Usage::TRANSFER_DST);\n'
         '\t{ ScopedBufferBind upload(this, buffer->As<CBuffer>());\n'
         '\t  glBufferData(GL_ARRAY_BUFFER, buffer->GetSize(), nullptr, GL_STREAM_DRAW);\n'
         '\t  glBufferSubData(GL_ARRAY_BUFFER, 0, dataSize, data); }\n'
         '\tSetVertexBuffer(bindingSlot, buffer.get(), 0);\n'
         '\treturn;\n#endif\n'
         '\tBindBuffer(CBuffer::Type::VERTEX, nullptr);')
    edit('renderer/backend/gl/DeviceCommandContext.cpp',
         'void CDeviceCommandContext::SetIndexBufferData(const void* data, const uint32_t dataSize)\n{\n\tENSURE(dataSize > 0);',
         'void CDeviceCommandContext::SetIndexBufferData(const void* data, const uint32_t dataSize)\n{\n\tENSURE(dataSize > 0);\n'
         '#if defined(__EMSCRIPTEN__)\n'
         '\tBindBuffer(CBuffer::Type::INDEX, nullptr);\n'
         '\tif (!m_BrowserIndexBuffer || m_BrowserIndexBuffer->GetSize() < dataSize)\n'
         '\t\tm_BrowserIndexBuffer = m_Device->CreateBuffer("browser transient indices", IBuffer::Type::INDEX, dataSize, IBuffer::Usage::DYNAMIC | IBuffer::Usage::TRANSFER_DST);\n'
         '\t{ ScopedBufferBind upload(this, m_BrowserIndexBuffer->As<CBuffer>());\n'
         '\t  glBufferData(GL_ELEMENT_ARRAY_BUFFER, m_BrowserIndexBuffer->GetSize(), nullptr, GL_STREAM_DRAW);\n'
         '\t  glBufferSubData(GL_ELEMENT_ARRAY_BUFFER, 0, dataSize, data); }\n'
         '\tSetIndexBuffer(m_BrowserIndexBuffer.get());\n'
         '\treturn;\n#endif')
    args.patch.parent.mkdir(parents=True, exist_ok=True)
    if changes:
        with args.patch.open('a') as stream:
            stream.write(''.join(changes))


if __name__ == '__main__':
    main()
