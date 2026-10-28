// Validate asynchronous device ownership through the pinned Emdawn C API.
// No game, render pipeline, shader or presentation is exercised here.
#include <webgpu/webgpu.h>
#include <emscripten.h>
#include <cstdio>

namespace
{
WGPUInstance instance;
WGPUAdapter adapter;
WGPUDevice device;
WGPUQueue queue;
WGPUBuffer buffer;
int exitCode;

void Finish(int code)
{
    if (buffer)
    {
        wgpuBufferDestroy(buffer);
        wgpuBufferRelease(buffer);
    }
    if (queue)
        wgpuQueueRelease(queue);
    if (device)
    {
        wgpuDeviceDestroy(device);
        wgpuDeviceRelease(device);
    }
    if (adapter)
        wgpuAdapterRelease(adapter);
    if (instance)
        wgpuInstanceRelease(instance);
    std::puts(code == 0 ? "WEBGPU_DEVICE_UPLOAD_DRAINED_NOT_ENGINE_INTEGRATED" : "WEBGPU_DEVICE_PROBE_FAILED");
    // Dawn invokes completion inside a Promise callback. ExitStatus must be
    // handled by Emscripten's event trampoline after that callback returns.
    exitCode = code;
    emscripten_async_call([](void*) { emscripten_force_exit(exitCode); }, nullptr, 0);
}

void QueueDone(WGPUQueueWorkDoneStatus status, void*, void*)
{
    Finish(status == WGPUQueueWorkDoneStatus_Success ? 0 : 3);
}

void DeviceReady(WGPURequestDeviceStatus status, WGPUDevice value, WGPUStringView, void*, void*)
{
    if (status != WGPURequestDeviceStatus_Success || !value)
    {
        Finish(2);
        return;
    }
    device = value;
    queue = wgpuDeviceGetQueue(device);
    WGPUBufferDescriptor desc = WGPU_BUFFER_DESCRIPTOR_INIT;
    desc.size = 256;
    desc.usage = WGPUBufferUsage_CopyDst | WGPUBufferUsage_Uniform;
    buffer = wgpuDeviceCreateBuffer(device, &desc);
    const unsigned int data[4] = {1, 2, 3, 4};
    wgpuQueueWriteBuffer(queue, buffer, 0, data, sizeof(data));
    wgpuQueueSubmit(queue, 0, nullptr);
    WGPUQueueWorkDoneCallbackInfo callback = WGPU_QUEUE_WORK_DONE_CALLBACK_INFO_INIT;
    callback.mode = WGPUCallbackMode_AllowSpontaneous;
    callback.callback = QueueDone;
    wgpuQueueOnSubmittedWorkDone(queue, callback);
}

void AdapterReady(WGPURequestAdapterStatus status, WGPUAdapter value, WGPUStringView, void*, void*)
{
    if (status != WGPURequestAdapterStatus_Success || !value)
    {
        Finish(1);
        return;
    }
    adapter = value;
    WGPURequestDeviceCallbackInfo callback = WGPU_REQUEST_DEVICE_CALLBACK_INFO_INIT;
    callback.mode = WGPUCallbackMode_AllowSpontaneous;
    callback.callback = DeviceReady;
    wgpuAdapterRequestDevice(adapter, nullptr, callback);
}
}

int main()
{
    EM_ASM({ console.log('WEBGPU_OWNER:' + globalThis.constructor.name); });
    instance = wgpuCreateInstance(nullptr);
    if (!instance)
        return 4;
    WGPURequestAdapterOptions options = WGPU_REQUEST_ADAPTER_OPTIONS_INIT;
    options.powerPreference = WGPUPowerPreference_HighPerformance;
    WGPURequestAdapterCallbackInfo callback = WGPU_REQUEST_ADAPTER_CALLBACK_INFO_INIT;
    callback.mode = WGPUCallbackMode_AllowSpontaneous;
    callback.callback = AdapterReady;
    wgpuInstanceRequestAdapter(instance, &options, callback);
    emscripten_exit_with_live_runtime();
}
