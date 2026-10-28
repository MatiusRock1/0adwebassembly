// RT64 as the runtime's renderer in a browser: an ultramodern::renderer::RendererContext that hands the game's display
// lists to RT64, which draws them through plume's WebGPU backend on the page's canvas.
//
// It is RecompFrontend's RT64Context without recompui: no menus, no texture packs and no settings to follow, so RT64
// runs with fixed ones (below). RT64 picks WebGPU itself in an Emscripten build, and its device belongs to the page's
// main thread: the program runs in pthreads (-sPROXY_TO_PTHREAD) and every plume call RT64 makes is run on the main
// thread (plume_device_thread.h), which does nothing else. The page must have a canvas with id "canvas", be served with
// the cross-origin isolation headers threads need, and get its WebGPU device from plume_webgpu_device.js (--pre-js).

#include "rt64_web_renderer.h"

#include "hle/rt64_application.h"
#include "ultramodern/ultramodern.hpp"

namespace {
    // RT64 keeps pointers to the RSP and RDP registers; a recomp runs the RSP itself, so these only have to exist.
    uint8_t DMEM[0x1000];
    uint8_t IMEM[0x1000];
    uint8_t rom_header[0x40];
    uint32_t MI_INTR_REG = 0;
    uint32_t DPC_START_REG = 0;
    uint32_t DPC_END_REG = 0;
    uint32_t DPC_CURRENT_REG = 0;
    uint32_t DPC_STATUS_REG = 0;
    uint32_t DPC_CLOCK_REG = 0;
    uint32_t DPC_BUFBUSY_REG = 0;
    uint32_t DPC_PIPEBUSY_REG = 0;
    uint32_t DPC_TMEM_REG = 0;

    void check_interrupts() {}

    class RT64WebRenderer : public ultramodern::renderer::RendererContext {
    public:
        RT64WebRenderer(uint8_t *rdram, bool render_to_ram) {
            RT64::Application::Core core{};
            core.window = "#canvas";
            core.checkInterrupts = check_interrupts;
            core.HEADER = rom_header;
            core.RDRAM = rdram;
            core.DMEM = DMEM;
            core.IMEM = IMEM;
            core.MI_INTR_REG = &MI_INTR_REG;
            core.DPC_START_REG = &DPC_START_REG;
            core.DPC_END_REG = &DPC_END_REG;
            core.DPC_CURRENT_REG = &DPC_CURRENT_REG;
            core.DPC_STATUS_REG = &DPC_STATUS_REG;
            core.DPC_CLOCK_REG = &DPC_CLOCK_REG;
            core.DPC_BUFBUSY_REG = &DPC_BUFBUSY_REG;
            core.DPC_PIPEBUSY_REG = &DPC_PIPEBUSY_REG;
            core.DPC_TMEM_REG = &DPC_TMEM_REG;

            ultramodern::renderer::ViRegs *vi = ultramodern::renderer::get_vi_regs();
            core.VI_STATUS_REG = &vi->VI_STATUS_REG;
            core.VI_ORIGIN_REG = &vi->VI_ORIGIN_REG;
            core.VI_WIDTH_REG = &vi->VI_WIDTH_REG;
            core.VI_INTR_REG = &vi->VI_INTR_REG;
            core.VI_V_CURRENT_LINE_REG = &vi->VI_V_CURRENT_LINE_REG;
            core.VI_TIMING_REG = &vi->VI_TIMING_REG;
            core.VI_V_SYNC_REG = &vi->VI_V_SYNC_REG;
            core.VI_H_SYNC_REG = &vi->VI_H_SYNC_REG;
            core.VI_LEAP_REG = &vi->VI_LEAP_REG;
            core.VI_H_START_REG = &vi->VI_H_START_REG;
            core.VI_V_START_REG = &vi->VI_V_START_REG;
            core.VI_V_BURST_REG = &vi->VI_V_BURST_REG;
            core.VI_X_SCALE_REG = &vi->VI_X_SCALE_REG;
            core.VI_Y_SCALE_REG = &vi->VI_Y_SCALE_REG;

            RT64::ApplicationConfiguration app_config;
            app_config.useConfigurationFile = false;
            app = std::make_unique<RT64::Application>(core, app_config);
            app->emulatorConfig.framebuffer.renderToRAM = render_to_ram;

            // The defaults of a recomp's settings: the canvas's resolution in whole multiples of 240 lines, the original
            // aspect ratio, no MSAA (WebGPU has no sample positions), and the game's own frame pacing.
            app->userConfig.resolution = RT64::UserConfiguration::Resolution::WindowIntegerScale;
            app->userConfig.downsampleMultiplier = 1;
            app->userConfig.aspectRatio = RT64::UserConfiguration::AspectRatio::Original;
            app->userConfig.extAspectRatio = RT64::UserConfiguration::AspectRatio::Original;
            app->userConfig.antialiasing = RT64::UserConfiguration::Antialiasing::None;
            app->userConfig.refreshRate = RT64::UserConfiguration::RefreshRate::Original;
            app->userConfig.internalColorFormat = RT64::UserConfiguration::InternalColorFormat::Standard;
            app->userConfig.displayBuffering = RT64::UserConfiguration::DisplayBuffering::Triple;
            app->enhancementConfig.f3dex.forceBranch = true;
            app->enhancementConfig.textureLOD.scale = true;

            RT64::Application::SetupResult result = app->setup(0);
            if (result != RT64::Application::SetupResult::Success) {
                fprintf(stderr, "RT64 could not start on WebGPU (%d).\n", int(result));
                setup_result = ultramodern::renderer::SetupResult::GraphicsDeviceNotFound;
                app.reset();
                return;
            }

            setup_result = ultramodern::renderer::SetupResult::Success;
            chosen_api = ultramodern::renderer::GraphicsApi::Auto;
        }

        bool valid() override {
            return app != nullptr;
        }

        bool update_config(const ultramodern::renderer::GraphicsConfig &, const ultramodern::renderer::GraphicsConfig &) override {
            return false;
        }

        void enable_instant_present() override {
            app->enhancementConfig.presentation.mode = RT64::EnhancementConfiguration::Presentation::Mode::PresentEarly;
            app->updateEnhancementConfig();
        }

        void send_dl(const OSTask *task) override {
            app->state->rsp->reset();
            app->interpreter->loadUCodeGBI(task->t.ucode & 0x3FFFFFF, task->t.ucode_data & 0x3FFFFFF, true);
            app->processDisplayLists(app->core.RDRAM, task->t.data_ptr & 0x3FFFFFF, 0, true);
        }

        void send_dummy_workload(uint32_t fb_address) override {
            // As RT64Context: a fill of the frame buffer, for the runtime's first retraces before the game draws.
            app->state->listProcessBegin();
            app->state->rdp->setColorImage(G_IM_FMT_RGBA, G_IM_SIZ_16b, 320, fb_address);
            app->state->rdp->setOtherMode(0x382C30, 0);
            app->state->rdp->fillRect(0, 0, 320 << 2, 240 << 2);
            app->state->fullSync();
            app->state->listProcessEnd();
        }

        void update_screen() override {
            app->updateScreen();
        }

        void shutdown() override {
            if (app != nullptr) {
                app->end();
            }
        }

        uint32_t get_display_framerate() const override {
            return app->presentQueue->ext.sharedResources->swapChainRate;
        }

        float get_resolution_scale() const override {
            const int reference_height = 240;
            const uint32_t height = app->sharedQueueResources->swapChainHeight;
            return (height > 0) ? std::max(float((height + reference_height - 1) / reference_height), 1.0f) : 1.0f;
        }

    private:
        std::unique_ptr<RT64::Application> app;
    };
}

namespace recompweb {
    std::unique_ptr<ultramodern::renderer::RendererContext> create_rt64_renderer(uint8_t *rdram, bool render_to_ram) {
        return std::make_unique<RT64WebRenderer>(rdram, render_to_ram);
    }
}
