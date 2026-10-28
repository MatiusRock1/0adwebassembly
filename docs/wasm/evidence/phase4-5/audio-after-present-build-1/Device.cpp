/* Copyright (C) 2026 Wildfire Games.
 * This file is part of 0 A.D., licensed under GPL-2.0-or-later.
 * WebGPU implementation of the original backend interfaces.
 */
#include "precompiled.h"
#include "Device.h"
#include "CommandQueue.h"
#include "CommandData.h"
#include "application-deferred-audio.h"
#include "application-deferred-replay.h"
#include "graphics/ShaderDefines.h"
#include "ps/CLogger.h"
#include "renderer/backend/IFramebuffer.h"
#include "renderer/backend/IDeviceCommandContext.h"
#include "renderer/backend/IShaderProgram.h"
#include "renderer/backend/ISwapChain.h"
#include "renderer/backend/PipelineState.h"
#include "renderer/backend/Sampler.h"
#include "scriptinterface/Object.h"
#include <emscripten.h>
#include <emscripten/threading.h>
#include <atomic>
#include <array>
#include <charconv>
#include <cstring>
#include <limits>
#include <initializer_list>
#include <map>
#include <sstream>
#include <vector>
#include <SDL_video.h>

namespace Renderer::Backend::WebGPU
{
namespace
{
using S = std::string;
S Quote(const S& value)
{
    S out = "\"";
    for (unsigned char c : value)
    {
        if (c == '"' || c == '\\') { out += '\\'; out += c; }
        else if (c == '\n') out += "\\n";
        else if (c == '\r') out += "\\r";
        else if (c == '\t') out += "\\t";
        else if (c >= 32) out += c;
    }
    return out + '"';
}
template<typename T> S Num(T value)
{
    if constexpr(std::is_floating_point_v<T>)
    {
        // Preserve the original engine's float values across JSON. Six decimal
        // places can round small projection/normal coefficients to zero.
        char text[64];
        const auto result=std::to_chars(text,text+sizeof(text),value,
            std::chars_format::general,std::numeric_limits<T>::max_digits10);
        ENSURE(result.ec==std::errc{});
        return S(text,result.ptr);
    }
    else return std::to_string(value);
}
template<typename T> S Array(const T* values, size_t size)
{
    S out = "[";
    for (size_t i = 0; i < size; ++i) { if (i) out += ','; out += Num(values[i]); }
    return out + ']';
}
// Only the original renderer thread records backend calls. Every batch owns
// its strings/bytes until the browser acknowledges consumption. Synchronous
// resource operations and idle/destruction explicitly drain this bounded queue.
CommandQueue asyncCalls(6,32*1024*1024);
void WaitForAsyncCall(CommandQueue::Call& call)
{
    emscripten_current_thread_process_queued_calls();
    emscripten_futex_wait(&call.ready, 0, 100);
}
void ReclaimAsyncCalls(bool wait)
{
    asyncCalls.Reclaim(wait,WaitForAsyncCall);
}
void CallAsync(const char* method, const S& args = "[]", const void* data = nullptr, size_t size = 0)
{
    auto& owned = asyncCalls.Enqueue(method,args,std::span(static_cast<const uint8_t*>(data),size),WaitForAsyncCall);
    MAIN_THREAD_ASYNC_EM_ASM({
        const acknowledge = success => { Atomics.store(HEAP32,$5 >>> 2,success?1:2);Atomics.notify(HEAP32,$5 >>> 2); };
        const fail = error => { err(error.stack || String(error)); abort(String(error)); };
        const backend = Module.webgpuBackend;
        if (!backend) { acknowledge(false);fail(new Error('Missing WebGPU engine bridge'));return; }
        backend.commandDispatcher.enqueue(() => {
            if ((((Module.webgpuAsyncSequence || 0) + 1) >>> 0) !== ($4 >>> 0)) throw new Error('WebGPU asynchronous command order changed');
            Module.webgpuAsyncSequence = $4 >>> 0;
            backend.heap = () => HEAPU8;
            const pointer = $2 >>> 0;
            backend.call(UTF8ToString($0 >>> 0),JSON.parse(UTF8ToString($1 >>> 0)),HEAPU8.subarray(pointer,pointer+($3 >>> 0)));
        }, acknowledge, fail);
    }, owned.method.c_str(), owned.args.c_str(), owned.data.data(), owned.data.size(), owned.sequence, &owned.ready);
}
int Call(const char* method, const S& args = "[]", const void* data = nullptr, size_t size = 0)
{
    ReclaimAsyncCalls(true);
    return MAIN_THREAD_EM_ASM_INT({
        const backend = Module.webgpuBackend;
        if (!backend) { err('WebGPU engine bridge was not initialized'); abort('Missing WebGPU engine bridge'); }
        backend.heap = () => HEAPU8;
        try { return backend.call(UTF8ToString($0), JSON.parse(UTF8ToString($1)), HEAPU8.subarray($2, $2 + $3)) || 0; }
        catch (error) { err(error.stack || String(error)); abort(String(error)); }
    }, method, args.c_str(), data, size);
}
void Wait(const char* method, S args = "[")
{
    alignas(4) std::atomic<int> ready{0};
    Call(method, args + Num(reinterpret_cast<uintptr_t>(&ready)) + ']');
    while (!ready.load())
    {
        emscripten_current_thread_process_queued_calls();
        emscripten_futex_wait(&ready, 0, 100);
    }
    ENSURE(ready.load() == 1);
}

template<class Base> class Object : public Base
{
public:
    Object(CDevice* device, int handle) : owner(device), id(handle) {}
    ~Object() override { if (id > 0) CallAsync("release", '[' + Num(id) + ']'); }
    IDevice* GetDevice() override { return owner; }
    CDevice* owner;
    int id;
};
class Buffer final : public Object<IBuffer>
{
public:
    Buffer(CDevice* d, int id, Type t, uint32_t size, uint32_t usage) : Object(d,id), type(t), size(size), usage(usage), bytes(size) {}
    Type GetType() const override { return type; }
    uint32_t GetSize() const override { return size; }
    uint32_t GetUsage() const override { return usage; }
    Type type; uint32_t size, usage;
    std::vector<uint8_t> bytes;
};
class Texture final : public Object<ITexture>
{
public:
    Texture(CDevice* d, int id, Type t, uint32_t usage, Format f, uint32_t w, uint32_t h, uint32_t mips) : Object(d,id), type(t), usage(usage), format(f), width(w), height(h), mips(mips) {}
    Type GetType() const override { return type; }
    uint32_t GetUsage() const override { return usage; }
    Format GetFormat() const override { return format; }
    uint32_t GetWidth() const override { return width; }
    uint32_t GetHeight() const override { return height; }
    uint32_t GetMIPLevelCount() const override { return mips; }
    Type type; uint32_t usage; Format format; uint32_t width,height,mips;
};
class Framebuffer final : public Object<IFramebuffer>
{
public:
    Framebuffer(CDevice* d, int id, uint32_t w, uint32_t h, CColor c = {}) : Object(d,id), width(w),height(h),color(c) {}
    const CColor& GetClearColor() const override { return color; }
    uint32_t GetWidth() const override { return width; }
    uint32_t GetHeight() const override { return height; }
    uint32_t width,height; CColor color;
};
class Shader final : public Object<IShaderProgram>
{
public:
    using Object::Object;
    int32_t GetBindingSlot(const CStrIntern name) const override
    {
        auto it=slots.find(name);
        if(it!=slots.end())return it->second;
        const int32_t slot=Call("binding", '[' + Num(id) + ',' + Quote(name.string()) + ']');
        slots.emplace(name,slot);
        return slot;
    }
    std::vector<VfsPath> GetFileDependencies() const override { return {}; }
    mutable std::map<CStrIntern,int32_t> slots;
};
class Layout final : public Object<IVertexInputLayout> { public: using Object::Object; };
class GraphicsPipeline final : public Object<IGraphicsPipelineState>
{
public:
    GraphicsPipeline(CDevice* d, int id, IShaderProgram* shader) : Object(d,id), shader(shader) {}
    IShaderProgram* GetShaderProgram() const override { return shader; }
    IShaderProgram* shader;
};
class ComputePipeline final : public Object<IComputePipelineState>
{
public:
    ComputePipeline(CDevice* d, int id, IShaderProgram* shader) : Object(d,id), shader(shader) {}
    IShaderProgram* GetShaderProgram() const override { return shader; }
    IShaderProgram* shader;
};
class SwapChain final : public Object<ISwapChain>
{
public:
    SwapChain(CDevice* d, uint32_t w, uint32_t h) : Object(d,0), width(w),height(h) {}
    bool IsValid() const override { return owner->IsLive(); }
    // CreateSwapChain already resized the owned presentation images. Browser
    // image acquisition remains in Present, where that image is copied/submitted.
    bool AcquireNextBackbuffer() override { return owner->IsLive(); }
    IFramebuffer* GetCurrentBackbuffer(AttachmentLoadOp cl, AttachmentStoreOp cs, AttachmentLoadOp dl, AttachmentStoreOp ds) override
    {
        const std::array<int,4> key{int(cl),int(cs),int(dl),int(ds)};
        auto it=framebuffers.find(key);
        if(it!=framebuffers.end())return it->second.get();
        const int id=Call("backbuffer", '[' + Num(int(cl)) + ',' + Num(int(cs)) + ',' + Num(int(dl)) + ',' + Num(int(ds)) + ']');
        return framebuffers.emplace(key,std::make_unique<Framebuffer>(owner,id,width,height)).first->second.get();
    }
    void Present() override { CallAsync("present"); }
    uint32_t width,height;
    std::map<std::array<int,4>,std::unique_ptr<Framebuffer>> framebuffers;
};

class Context final : public Object<IDeviceCommandContext>
{
public:
    enum class Op : uint32_t { Pipeline=0,Layout=1,Vertex=2,Index=3,Uniform=4,Texture=5,StorageTexture=6,StorageBuffer=7,Draw=8,DrawIndexed=9,VertexData=10,IndexData=11,UploadBuffer=12,UploadTexture=13 };
    Context(CDevice* d) : Object(d,0) { commands.reserve(256*1024);commandData.reserve(1024*1024); }
    ~Context() override { Flush(); ReclaimAsyncCalls(true); }
    void Record(const char* name, const S& args = "[]")
    {
        FlushBinaryCommands();
        RecordJSON(name,args);
        MaybeFlushCommands();
    }
    void RecordJSON(const char* name,const S& args)
    {
        // Names are the fixed internal opcodes below, never user strings.
        // Append in place rather than allocate/escape several strings for
        // every state change, and retain the outer array across frames.
        if(commands.size()>1)commands+=',';
        commands+="[\"";commands+=name;commands+="\",";commands+=args;commands+=']';
    }
    void RecordWords(Op op,std::initializer_list<uint32_t> values)
    {
        binaryCommands.push_back(static_cast<uint32_t>(op));
        binaryCommands.insert(binaryCommands.end(),values);
        MaybeFlushCommands();
    }
    void FlushBinaryCommands()
    {
        if(binaryCommands.empty())return;
        const size_t offset=AppendData(binaryCommands.data(),binaryCommands.size()*sizeof(uint32_t));
        RecordJSON("binaryCommands",'['+Num(offset)+','+Num(binaryCommands.size())+']');
        binaryCommands.clear();
    }
    void SetGraphicsPipelineState(IGraphicsPipelineState* p) override { RecordWords(Op::Pipeline,{uint32_t(p->As<GraphicsPipeline>()->id)}); }
    void SetComputePipelineState(IComputePipelineState* p) override { Record("computePipeline", '[' + Num(p->As<ComputePipeline>()->id) + ']'); }
    void BlitFramebuffer(IFramebuffer* s,IFramebuffer* d,const Rect& sr,const Rect& dr,Sampler::Filter f) override
    { Record("blit", '[' + Num(s->As<Framebuffer>()->id) + ',' + Num(d->As<Framebuffer>()->id) + ',' + RectJSON(sr) + ',' + RectJSON(dr) + ',' + Num(int(f)) + ']'); }
    void ResolveFramebuffer(IFramebuffer* s,IFramebuffer* d) override { Record("resolve", '[' + Num(s->As<Framebuffer>()->id) + ',' + Num(d->As<Framebuffer>()->id) + ']'); }
    void BeginFramebufferPass(IFramebuffer* p) override { Record("beginFramebuffer", '[' + Num(p->As<Framebuffer>()->id) + ']'); }
    void EndFramebufferPass() override { Record("endFramebuffer"); }
    void ClearFramebuffer(bool c,bool d,bool s) override { Record("clear", '[' + Num(c) + ',' + Num(d) + ',' + Num(s) + ']'); }
    void ReadbackFramebufferSync(ISwapChain&,uint32_t x,uint32_t y,uint32_t w,uint32_t h,void* data) override
    { Flush(); Wait("readback", '[' + Num(x) + ',' + Num(y) + ',' + Num(w) + ',' + Num(h) + ',' + Num(reinterpret_cast<uintptr_t>(data)) + ','); }
    void UploadTexture(ITexture* t,Format f,const void* data,size_t size,uint32_t level,uint32_t layer) override
    { UploadTextureRegion(t,f,data,size,0,0,std::max(1u,t->GetWidth() >> level),std::max(1u,t->GetHeight() >> level),level,layer); }
    void UploadTextureRegion(ITexture* t,Format f,const void* data,size_t size,uint32_t x,uint32_t y,uint32_t w,uint32_t h,uint32_t level,uint32_t layer) override
    {
        // Texture uploads need no browser-generated result. Keep their bytes
        // in the ordered packet, like buffer uploads, instead of draining the
        // preceding frame for a synchronous staging-object allocation.
        const uint32_t dataOffset=AppendData(data,size);
        RecordWords(Op::UploadTexture,{uint32_t(t->As<Texture>()->id),uint32_t(f),x,y,w,h,level,layer,dataOffset,uint32_t(size)});
    }
    void UploadBuffer(IBuffer* b,const void* data,uint32_t size) override { UploadBufferRegion(b,data,0,size); }
    void UploadBuffer(IBuffer* b,const UploadBufferFunction& f) override { UploadBufferRegion(b,0,b->GetSize(),f); }
    void UploadBufferRegion(IBuffer* b,const void* data,uint32_t offset,uint32_t size) override
    {
        auto* buffer = b->As<Buffer>(); ENSURE(offset <= buffer->size && size <= buffer->size-offset);
        std::memcpy(buffer->bytes.data()+offset,data,size);
        // The API accepts 4-byte aligned writes; keep a CPU mirror to preserve
        // neighboring bytes when engine index ranges contain an odd uint16.
        const auto upload = AppendUploadBytes(commandData,buffer->bytes,offset,size);
        // Keep each ordered upload in the same immutable batch as its draws.
        // The browser stages those bytes in a reusable COPY_SRC arena instead
        // of a synchronous proxy call and a fresh GPU buffer for each upload.
        RecordWords(Op::UploadBuffer,{uint32_t(buffer->id),upload.bufferOffset,upload.dataOffset,upload.byteSize});
    }
    void UploadBufferRegion(IBuffer* b,uint32_t offset,uint32_t size,const UploadBufferFunction& f) override
    { std::vector<uint8_t> bytes(size); f(bytes.data()); UploadBufferRegion(b,bytes.data(),offset,size); }
    static S RectJSON(const Rect& r) { return '[' + Num(r.x)+','+Num(r.y)+','+Num(r.width)+','+Num(r.height)+']'; }
    void SetScissors(uint32_t n,const Rect* r) override { ENSURE(n <= 1); Record("scissor", n ? RectJSON(*r) : "[]"); }
    void SetViewports(uint32_t n,const Rect* r) override { ENSURE(n == 1); Record("viewport",RectJSON(*r)); }
    void SetVertexInputLayout(IVertexInputLayout* p) override { RecordWords(Op::Layout,{uint32_t(p->As<Layout>()->id)}); }
    void SetVertexBuffer(uint32_t slot,IBuffer* b,uint32_t offset) override { RecordWords(Op::Vertex,{slot,uint32_t(b->As<Buffer>()->id),offset}); }
    void SetVertexBufferData(uint32_t slot,const void* data,uint32_t size) override
    {
        RecordWords(Op::VertexData,{slot,uint32_t(AppendData(data,size)),size});
    }
    void SetIndexBuffer(IBuffer* b) override { RecordWords(Op::Index,{uint32_t(b->As<Buffer>()->id)}); }
    void SetIndexBufferData(const void* data,uint32_t size) override
    {
        RecordWords(Op::IndexData,{uint32_t(AppendData(data,size)),size});
    }
    void BeginPass() override { Record("beginPass"); }
    void EndPass() override { Record("endPass"); }
    void Draw(uint32_t first,uint32_t count) override { DrawInstanced(first,count,0,1); }
    void DrawIndexed(uint32_t first,uint32_t count,int32_t offset) override { DrawIndexedInstanced(first,count,0,1,offset); }
    void DrawInstanced(uint32_t first,uint32_t count,uint32_t instance,uint32_t instances) override { RecordWords(Op::Draw,{first,count,instance,instances}); }
    void DrawIndexedInstanced(uint32_t first,uint32_t count,uint32_t instance,uint32_t instances,int32_t offset) override { RecordWords(Op::DrawIndexed,{first,count,instance,instances,uint32_t(offset)}); }
    void DrawIndexedInRange(uint32_t first,uint32_t count,uint32_t,uint32_t) override { DrawIndexed(first,count,0); }
    void BeginComputePass() override { Record("beginCompute"); }
    void EndComputePass() override { Record("endCompute"); }
    void Dispatch(uint32_t x,uint32_t y,uint32_t z) override { Record("dispatch", '['+Num(x)+','+Num(y)+','+Num(z)+']'); }
    void InsertMemoryBarrier(uint32_t,uint32_t,uint32_t,uint32_t) override { /* WebGPU pass/resource transitions are implicit. */ }
    void SetTexture(int32_t slot,ITexture* t) override { if(slot>=0) RecordWords(Op::Texture,{uint32_t(slot),uint32_t(t->As<Texture>()->id)}); }
    void SetStorageTexture(int32_t slot,ITexture* t) override { if(slot>=0) RecordWords(Op::StorageTexture,{uint32_t(slot),uint32_t(t->As<Texture>()->id)}); }
    void SetStorageBuffer(int32_t slot,IBuffer* b) override { if(slot>=0) RecordWords(Op::StorageBuffer,{uint32_t(slot),uint32_t(b->As<Buffer>()->id)}); }
    void SetUniform(int32_t slot,float x) override { SetUniform(slot,std::span(&x,1)); }
    void SetUniform(int32_t slot,float x,float y) override { float v[]={x,y};SetUniform(slot,v); }
    void SetUniform(int32_t slot,float x,float y,float z) override { float v[]={x,y,z};SetUniform(slot,v); }
    void SetUniform(int32_t slot,float x,float y,float z,float w) override { float v[]={x,y,z,w};SetUniform(slot,v); }
    void SetUniform(int32_t slot,std::span<const float> v) override
    {
        if(slot>=0) RecordWords(Op::Uniform,{uint32_t(slot),uint32_t(AppendData(v.data(),v.size_bytes())),uint32_t(v.size())});
    }
    void InsertTimestampQuery(uint32_t,bool) override { ENSURE(!owner->GetCapabilities().timestamps); }
    void BeginScopedLabel(const char* name) override { Record("pushLabel", '['+Quote(name)+']'); }
    void EndScopedLabel() override { Record("popLabel"); }
    void Flush() override
    {
        WasmApplication::replayFlushes.Drain();
        FlushCommands();
        transient.clear();
    }
    void MaybeFlushCommands()
    {
        if(commandData.size()>=1024*1024 || binaryCommands.size()>=32*1024)
            FlushCommands();
    }
    void FlushCommands()
    {
        FlushBinaryCommands();
        // The asynchronous bridge owns an additional immutable snapshot until
        // acknowledgement. The original renderer can begin its next update
        // while the browser encodes these commands; resource queries are fences.
        if(commands.size()>1)
        {
            commands+=']';
            CallAsync("commands",commands,commandData.data(),commandData.size());
            commands.resize(1);
        }
        commandData.clear();
    }
    size_t AppendData(const void* data,size_t size)
    {
        const size_t offset=(commandData.size()+3)&~size_t(3);
        ENSURE(offset<=std::numeric_limits<uint32_t>::max() && size<=std::numeric_limits<uint32_t>::max()-offset);
        commandData.resize(offset+size);
        if(size)std::memcpy(commandData.data()+offset,data,size);
        return offset;
    }
    S commands="[";
    std::vector<uint8_t> commandData;
    std::vector<uint32_t> binaryCommands;
    std::vector<std::unique_ptr<IBuffer>> transient;
};
}

CDevice::CDevice()
{
    m_Name="WebGPU";m_Version="1";m_DriverInformation="Browser WebGPU";
    m_Capabilities.S3TC=Call("feature", "[\"texture-compression-bc\"]");
    m_Capabilities.computeShaders=true;m_Capabilities.storage=true;
    m_Capabilities.debugLabels=true;m_Capabilities.debugScopedLabels=true;
    m_Capabilities.multisampling=true;m_Capabilities.maxSampleCount=4;
    m_Capabilities.anisotropicFiltering=true;m_Capabilities.maxAnisotropy=16;
    m_Capabilities.maxTextureSize=Call("limit", "[\"maxTextureDimension2D\"]");
    m_Capabilities.instancing=true;m_Capabilities.timestamps=false;
    Call("observeLive",'['+Num(reinterpret_cast<uintptr_t>(&m_Live))+",1]");
    WasmApplication::deferAudioIdle=true;
    WasmApplication::replayFlushes.enabled=true;
}
CDevice::~CDevice()
{
    WasmApplication::replayFlushes.Drain();WasmApplication::replayFlushes.enabled=false;
    WasmApplication::RunDeferredAudioIdle();WasmApplication::deferAudioIdle=false;
    WaitUntilIdle();
    Call("observeLive",'['+Num(reinterpret_cast<uintptr_t>(&m_Live))+",0]");
}
std::unique_ptr<IDevice> CDevice::Create(SDL_Window*) { if(!Call("valid"))return nullptr;return std::make_unique<CDevice>(); }
std::unique_ptr<IDevice> CreateDevice(SDL_Window* w) { return CDevice::Create(w); }
void CDevice::Report(const Script::Request& rq,JS::HandleValue settings) { Script::SetProperty(rq,settings,"name","webgpu"); }
void CDevice::WaitUntilIdle() { Wait("idle"); }
std::unique_ptr<IDeviceCommandContext> CDevice::CreateCommandContext() { return std::make_unique<Context>(this); }
std::unique_ptr<ISwapChain> CDevice::CreateSwapChain(const char*,SDL_Window* window,int w,int h,bool,std::unique_ptr<ISwapChain> old)
{
    // Surface dimensions are optional when an SDL window is supplied. During
    // initial VideoMode setup m_CurrentW/H have not been populated yet.
    if(window && (w<=0 || h<=0))SDL_GetWindowSize(window,&w,&h);
    ENSURE(w>0 && h>0);
    old.reset();Call("resize",'['+Num(w)+','+Num(h)+']');return std::make_unique<SwapChain>(this,w,h);
}
std::unique_ptr<IVertexInputLayout> CDevice::CreateVertexInputLayout(std::span<const SVertexAttributeFormat> attributes)
{
    S args="[";
    for(const auto& a:attributes){if(args.size()>1)args+=',';args+='['+Num(int(a.stream))+','+Num(int(a.format))+','+Num(a.offset)+','+Num(a.stride)+','+Num(int(a.rate))+','+Num(a.bindingSlot)+']';}
    return std::make_unique<Layout>(this,Call("createLayout",args+']'));
}
std::unique_ptr<IShaderProgram> CDevice::CreateShaderProgram(const CStr& name,const CShaderDefines& defines)
{
    S args='['+Quote(name)+",{";
    bool first=true;
    for(const auto& [key,value]:defines.GetMap()) {if(!first)args+=',';first=false;args+=Quote(key.string())+':'+Quote(value.string());}
    int id=Call("createShader",args+"}]");
    if(!id)return nullptr;
    return std::make_unique<Shader>(this,id);
}
std::unique_ptr<IBuffer> CDevice::CreateBuffer(const char* name,IBuffer::Type t,uint32_t size,uint32_t usage)
{return std::make_unique<Buffer>(this,Call("createBuffer",'['+Quote(name)+','+Num(int(t))+','+Num(size)+','+Num(usage)+']'),t,size,usage);}
std::unique_ptr<ITexture> CDevice::CreateTexture(const char* name,ITexture::Type t,uint32_t usage,Format f,uint32_t w,uint32_t h,const Sampler::Desc& s,uint32_t mips,uint32_t samples)
{
    S sampler='['+Num(int(s.magFilter))+','+Num(int(s.minFilter))+','+Num(int(s.mipFilter))+','+Num(int(s.addressModeU))+','+Num(int(s.addressModeV))+','+Num(int(s.addressModeW))+','+Num(s.anisotropyEnabled?s.maxAnisotropy:1)+','+Num(s.compareEnabled)+','+Num(int(s.compareOp))+','+Num(int(s.borderColor))+','+Num(s.mipLODBias)+']';
    int id=Call("createTexture",'['+Quote(name)+','+Num(int(t))+','+Num(usage)+','+Num(int(f))+','+Num(w)+','+Num(h)+','+sampler+','+Num(mips)+','+Num(samples)+']');
    return std::make_unique<Texture>(this,id,t,usage,f,w,h,mips);
}
std::unique_ptr<ITexture> CDevice::CreateTexture2D(const char* name,uint32_t usage,Format f,uint32_t w,uint32_t h,const Sampler::Desc& s,uint32_t mips,uint32_t samples)
{return CreateTexture(name,ITexture::Type::TEXTURE_2D,usage,f,w,h,s,mips,samples);}
std::unique_ptr<IFramebuffer> CDevice::CreateFramebuffer(const char* name,SColorAttachment* c,SDepthStencilAttachment* d)
{
    ITexture* t=c?c->texture:d->texture; CColor color=c?c->clearColor:CColor{};
    S args='['+Quote(name)+','+Num(c?c->texture->As<Texture>()->id:0)+','+Num(d?d->texture->As<Texture>()->id:0)+','+Num(c?int(c->loadOp):0)+','+Num(c?int(c->storeOp):0)+','+Num(d?int(d->loadOp):0)+','+Num(d?int(d->storeOp):0)+','+Array(&color.r,4)+']';
    return std::make_unique<Framebuffer>(this,Call("createFramebuffer",args),t->GetWidth(),t->GetHeight(),color);
}
std::unique_ptr<IGraphicsPipelineState> CDevice::CreateGraphicsPipelineState(const SGraphicsPipelineStateDesc& p)
{
    const auto& d=p.depthStencilState;const auto& b=p.blendState;const auto& r=p.rasterizationState;
    auto stencil=[](const SStencilOpState& s){return '['+Num(int(s.failOp))+','+Num(int(s.passOp))+','+Num(int(s.depthFailOp))+','+Num(int(s.compareOp))+']';};
    S args='['+Num(p.shaderProgram->As<Shader>()->id)+",["+Num(d.depthTestEnabled)+','+Num(int(d.depthCompareOp))+','+Num(d.depthWriteEnabled)+','+Num(d.stencilTestEnabled)+','+Num(d.stencilReadMask)+','+Num(d.stencilWriteMask)+','+Num(d.stencilReference)+','+stencil(d.stencilFrontFace)+','+stencil(d.stencilBackFace)+"],["+Num(b.enabled)+','+Num(int(b.srcColorBlendFactor))+','+Num(int(b.dstColorBlendFactor))+','+Num(int(b.colorBlendOp))+','+Num(int(b.srcAlphaBlendFactor))+','+Num(int(b.dstAlphaBlendFactor))+','+Num(int(b.alphaBlendOp))+','+Array(&b.constant.r,4)+','+Num(b.colorWriteMask)+"],["+Num(int(r.polygonMode))+','+Num(int(r.cullMode))+','+Num(int(r.frontFace))+','+Num(r.depthBiasEnabled)+','+Num(r.depthBiasConstantFactor)+','+Num(r.depthBiasSlopeFactor)+"]]";
    return std::make_unique<GraphicsPipeline>(this,Call("createPipeline",args),p.shaderProgram);
}
std::unique_ptr<IComputePipelineState> CDevice::CreateComputePipelineState(const SComputePipelineStateDesc& p)
{return std::make_unique<ComputePipeline>(this,Call("createComputePipeline",'['+Num(p.shaderProgram->As<Shader>()->id)+']'),p.shaderProgram);}
bool CDevice::IsTextureFormatSupported(Format f) const {return Call("formatSupported",'['+Num(int(f))+']');}
bool CDevice::IsFramebufferFormatSupported(Format f) const {return Call("attachmentSupported",'['+Num(int(f))+']');}
Format CDevice::GetPreferredDepthStencilFormat(uint32_t,bool depth,bool stencil) const {return depth?(stencil?Format::D24_UNORM_S8_UINT:Format::D32_SFLOAT):Format::UNDEFINED;}
uint32_t CDevice::AllocateQuery() {return 0;}
void CDevice::FreeQuery(uint32_t) {}
bool CDevice::IsQueryResultAvailable(uint32_t) const {return false;}
uint64_t CDevice::GetQueryResult(uint32_t) {return 0;}
}
