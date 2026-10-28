// Toolchain/link probe only: not a renderer, shader or game acceptance test.
#include <webgpu/webgpu.h>
#include <cstdio>

int main()
{
    WGPUInstance instance = wgpuCreateInstance(nullptr);
    if (!instance)
        return 1;
    std::puts("WEBGPU_INSTANCE_CREATED_NOT_ENGINE_INTEGRATED");
    wgpuInstanceRelease(instance);
    return 0;
}
