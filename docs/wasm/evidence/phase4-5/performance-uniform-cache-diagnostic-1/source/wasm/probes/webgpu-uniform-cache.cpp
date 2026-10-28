#include "renderer/backend/webgpu/UniformCache.h"
#include <array>
#include <iostream>
#include <map>
#include <stdexcept>

using Renderer::Backend::WebGPU::UniformCache;
void Check(bool ok) { if (!ok) throw std::runtime_error("Uniform cache probe failed"); }
template<size_t N> auto Bytes(const std::array<uint32_t,N>& words)
{ return std::span(reinterpret_cast<const uint8_t*>(words.data()),words.size()*4); }
int main()
{
    unsigned checks=0,cases=0,omitted=0;
    UniformCache cache;
    std::array<uint32_t,4> value{0,0x80000000,0x7fc00001,0x3f800000};
    Check(cache.Update(7,Bytes(value)) && !cache.Update(7,Bytes(value)));++checks;
    auto changed=value;changed[0]=0x80000000;
    Check(cache.Update(7,Bytes(changed)));changed[2]=0x7fc00002;
    Check(cache.Update(7,Bytes(changed)));++checks;
    Check(cache.Update(8,Bytes(changed)) && !cache.Update(7,Bytes(changed)));++checks;
    cache.Clear();Check(cache.Update(7,Bytes(changed)));++checks;
    Check(cache.Update(7,Bytes(changed).first(4)) && cache.Update(7,Bytes(changed)));++checks;
    value=changed;value[3]=123;
    Check(cache.Update(7,Bytes(value)) && cache.Update(7,Bytes(changed)));++checks;
    UniformCache bounded(16);
    Check(bounded.Update(1,Bytes(value)) && bounded.Update(2,Bytes(changed)) && bounded.Bytes()==16);
    Check(bounded.Update(1,Bytes(value)));std::array<uint32_t,5> large{};
    Check(bounded.Update(1,Bytes(large)) && bounded.Bytes()==0 && bounded.Update(1,Bytes(value)));++checks;
    // Compare the state seen at every simulated draw against an uncached
    // producer, including partial writes, packet/context fences and NaN bits.
    std::map<int,std::array<uint8_t,64>> expected,actual;
    uint32_t random=0x45ad45;
    for(unsigned frame=0;frame<64;++frame)
    {
        cache.Clear();
        for(unsigned draw=0;draw<512;++draw)
        {
            random=random*1664525+1013904223;
            const int slot=(random>>16)%9;
            std::array<uint32_t,16> words{};
            for(unsigned i=0;i<16;++i)words[i]=(draw%5==0)?random+i:uint32_t(slot+i);
            const size_t count=1+((random>>20)%16);
            const auto bytes=Bytes(words).first(count*4);
            std::memcpy(expected[slot].data(),bytes.data(),bytes.size());
            if(cache.Update(slot,bytes))std::memcpy(actual[slot].data(),bytes.data(),bytes.size());else ++omitted;
            Check(actual==expected);++cases;
            if(draw%73==0){cache.Clear();expected[slot].fill(0x5b);actual[slot].fill(0x5b);}
        }
    }
    Check(omitted>0);++checks;
    std::cout<<"{\"passed\":true,\"checks\":"<<checks<<",\"differentialDraws\":"<<cases<<",\"omittedWrites\":"<<omitted<<"}\n";
}
