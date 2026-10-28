#pragma once
#include <memory>
struct SDL_Window;
namespace Renderer::Backend { class IDevice; }
namespace Renderer::Backend::WebGPU { std::unique_ptr<IDevice> CreateDevice(SDL_Window*); }
