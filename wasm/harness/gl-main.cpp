// Diagnostic only: exercise SDL and the original GL/GLES backend in WebGL 2.
#include "lib/external_libraries/libsdl.h"
#include "lib/timer.h"
#include "ps/ConfigDB.h"
#include "ps/ThreadUtil.h"
#include "renderer/backend/gl/Device.h"
#include "renderer/backend/IDeviceCommandContext.h"
#include "renderer/backend/ISwapChain.h"
#include <emscripten/html5.h>
#include <cstdio>

int main()
{
    Threading::SetMainThread();
    timer_Init();
    CConfigDB config;
    if (SDL_Init(SDL_INIT_VIDEO) < 0) return 20;
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_ES);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 3);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 0);
    SDL_Window* window = SDL_CreateWindow("0 A.D. WebGL 2", 0, 0, 640, 480, 0);
    if (!window) { std::fprintf(stderr, "SDL window: %s\n", SDL_GetError()); return 21; }
    if (SDL_GL_LoadLibrary(nullptr) < 0) return 24;
    EmscriptenWebGLContextAttributes attributes;
    emscripten_webgl_init_context_attributes(&attributes);
    attributes.majorVersion = 2;
    attributes.alpha = false;
    attributes.antialias = false;
    attributes.explicitSwapControl = true;
    attributes.renderViaOffscreenBackBuffer = true;
    attributes.proxyContextToMainThread = EMSCRIPTEN_WEBGL_CONTEXT_PROXY_ALWAYS;
    const auto webgl = emscripten_webgl_create_context("#canvas", &attributes);
    if (webgl <= 0 || emscripten_webgl_make_context_current(webgl) != EMSCRIPTEN_RESULT_SUCCESS) return 25;
    {
        // The backend supports an externally owned context (also used by Atlas).
        auto device = Renderer::Backend::GL::CDevice::Create(nullptr);
        if (!device) return 22;
        auto context = device->CreateCommandContext();
        auto swapChain = device->CreateSwapChain("browser", nullptr, 640, 480, false, nullptr);
        if (!context || !swapChain || !swapChain->AcquireNextBackbuffer()) return 23;
        using namespace Renderer::Backend;
        context->BeginFramebufferPass(swapChain->GetCurrentBackbuffer(
            AttachmentLoadOp::CLEAR, AttachmentStoreOp::STORE,
            AttachmentLoadOp::CLEAR, AttachmentStoreOp::STORE));
        context->ClearFramebuffer(true, true, false);
        context->EndFramebufferPass();
        context->Flush();
        swapChain->Present();
        if (emscripten_webgl_commit_frame() != EMSCRIPTEN_RESULT_SUCCESS) return 26;
        device->WaitUntilIdle();
        std::printf("GL_ENGINE_CLEAR_PASSED %s\n", device->GetVersion().c_str());
    }
    emscripten_webgl_destroy_context(webgl);
    SDL_DestroyWindow(window);
    SDL_Quit();
    return 0;
}
