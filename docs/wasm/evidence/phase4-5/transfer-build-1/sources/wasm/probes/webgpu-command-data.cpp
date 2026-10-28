#include "renderer/backend/webgpu/CommandData.h"
#include <iostream>

using Renderer::Backend::WebGPU::AppendUploadBytes;
using Renderer::Backend::WebGPU::AppendGeneratedUpload;
void Check(bool ok) { if (!ok) throw std::runtime_error("Command data probe failed"); }
int main()
{
    unsigned checks = 0, cases = 0;
    // Differentially compare every range of small odd/even buffers and all
    // packet alignments against the previous producer, including zero writes.
    for (uint32_t size = 0; size <= 65; ++size)
        for (uint32_t offset = 0; offset <= size; ++offset)
            for (uint32_t count = 0; count <= size-offset; ++count)
                for (uint32_t prefix = 0; prefix < 4; ++prefix)
                {
                    std::vector<uint8_t> mirror(size);
                    for (uint32_t i = 0; i < size; ++i) mirror[i] = uint8_t(i*31+size);
                    const uint32_t start = offset & ~3u, end = (offset+count+3)&~3u;
                    std::vector<uint8_t> oldUpload(end-start,0);
                    if (end>start) std::memcpy(oldUpload.data(),mirror.data()+start,std::min(end,size)-start);
                    std::vector<uint8_t> oldPacket(prefix,0x7b), packet=oldPacket;
                    const auto expectedOffset=(oldPacket.size()+3)&~size_t(3);
                    oldPacket.resize(expectedOffset+oldUpload.size(),0);
                    if (!oldUpload.empty()) std::memcpy(oldPacket.data()+expectedOffset,oldUpload.data(),oldUpload.size());
                    const auto upload=AppendUploadBytes(packet,mirror,offset,count);
                    Check(packet==oldPacket && upload.bufferOffset==start && upload.byteSize==end-start && upload.dataOffset==expectedOffset);
                    ++cases;
                }
    ++checks;
    std::vector<uint8_t> mirror{1,2,3,4,5}, packet;
    const auto first=AppendUploadBytes(packet,mirror,1,1);mirror[1]=99;
    Check(std::vector<uint8_t>(packet.begin()+first.dataOffset,packet.end())==std::vector<uint8_t>({1,2,3,4}));++checks;
    const auto second=AppendUploadBytes(packet,mirror,4,1);
    Check(second.dataOffset==4 && std::vector<uint8_t>(packet.begin()+4,packet.end())==std::vector<uint8_t>({5,0,0,0}));++checks;
    bool rejected=false;try{AppendUploadBytes(packet,mirror,6,0);}catch(const std::out_of_range&){rejected=true;}
    Check(rejected);++checks;
    rejected=false;try{AppendUploadBytes(packet,mirror,4,2);}catch(const std::out_of_range&){rejected=true;}
    Check(rejected);++checks;
    unsigned generatedCases=0;
    for (uint32_t length=0;length<=65;++length)
        for (uint32_t offset=0;offset<=length;++offset)
            for (uint32_t count=0;count<=length-offset;++count)
                for (uint32_t prefix=0;prefix<4;++prefix)
                {
                    std::vector<uint8_t> oldMirror(length), nextMirror;
                    for(uint32_t i=0;i<length;++i) oldMirror[i]=uint8_t(i*17+length);
                    nextMirror=oldMirror;
                    std::vector<uint8_t> oldPacket(prefix,123),nextPacket=oldPacket;
                    auto fill=[count](uint8_t* destination) {
                        // Partial writers must still get the old zero initialization.
                        for(uint32_t i=0;i<count;i+=2) destination[i]=uint8_t(i*13+7);
                    };
                    std::vector<uint8_t> temporary(count,0);fill(temporary.data());
                    if(count)std::memcpy(oldMirror.data()+offset,temporary.data(),count);
                    const auto oldUpload=AppendUploadBytes(oldPacket,oldMirror,offset,count);
                    const auto nextUpload=AppendGeneratedUpload(nextPacket,nextMirror,offset,count,fill);
                    Check(oldMirror==nextMirror && oldPacket==nextPacket && oldUpload.dataOffset==nextUpload.dataOffset &&
                        oldUpload.bufferOffset==nextUpload.bufferOffset && oldUpload.byteSize==nextUpload.byteSize);
                    ++generatedCases;
                }
    ++checks;
    const auto beforeMirror=mirror,beforePacket=packet;
    rejected=false;
    try{AppendGeneratedUpload(packet,mirror,1,3,[](uint8_t* p){p[0]=255;throw std::runtime_error("writer");});}
    catch(const std::runtime_error&){rejected=true;}
    Check(rejected && mirror==beforeMirror && packet==beforePacket);++checks;
    rejected=false;
    try{AppendGeneratedUpload(packet,mirror,4,2,[](uint8_t*){throw std::logic_error("must not invoke writer");});}
    catch(const std::out_of_range&){rejected=true;}
    Check(rejected && mirror==beforeMirror && packet==beforePacket);++checks;
    std::cout<<"{\"passed\":true,\"checks\":"<<checks<<",\"differentialCases\":"<<cases<<",\"generatedCases\":"<<generatedCases<<"}\n";
}
