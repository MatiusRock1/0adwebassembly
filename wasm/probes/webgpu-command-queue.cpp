#include "renderer/backend/webgpu/CommandQueue.h"
#include <iostream>
#include <thread>

using Renderer::Backend::WebGPU::CommandQueue;
void Check(bool condition) { if (!condition) throw std::runtime_error("Command queue probe failed"); }
int main()
{
    unsigned checks=0;
    std::vector<uint32_t> consumed;
    auto wait=[&](CommandQueue::Call& call){consumed.push_back(call.sequence);call.ready.store(1);};
    CommandQueue queue(2,8);
    std::vector<uint8_t> data{1,2,3,4};std::string args="[1]";
    auto& first=queue.Enqueue("commands",args,data,wait);
    args="[9]";data[0]=9;
    Check(first.args=="[1]" && first.data==std::vector<uint8_t>({1,2,3,4}));++checks;
    auto& second=queue.Enqueue("present","[]",data,wait);
    second.ready.store(1);queue.Reclaim(false,wait);
    Check(queue.PendingCount()==2 && queue.PendingBytes()==8);++checks;
    first.ready.store(1);queue.Reclaim(false,wait);
    Check(!queue.PendingCount() && !queue.PendingBytes());++checks;
    queue.Enqueue("commands","[]",data,wait);queue.Enqueue("present","[]",data,wait);
    auto& fifth=queue.Enqueue("release","[1]",data,wait);
    Check(consumed==std::vector<uint32_t>({3,4}) && fifth.sequence==5 && queue.PendingCount()==1);++checks;
    queue.Reclaim(false,wait);Check(queue.PendingCount()==1);++checks;
    queue.Reclaim(true,wait);Check(!queue.PendingCount() && consumed.back()==5);++checks;
    CommandQueue bytes(64,4);
    bytes.Enqueue("commands","[]",data,wait);bytes.Enqueue("present","[]",data,wait);
    Check(bytes.PendingCount()==1 && bytes.PendingBytes()==4);++checks;bytes.Reclaim(true,wait);
    CommandQueue oversized(64,2);
    oversized.Enqueue("commands","[]",data,wait);oversized.Enqueue("present","[]",{},wait);
    Check(oversized.PendingCount()==1 && !oversized.PendingBytes());++checks;oversized.Reclaim(true,wait);
    CommandQueue threaded;
    auto& pending=threaded.Enqueue("commands","[]",data,wait);
    std::thread browser([&]{Check(pending.data==data);pending.ready.store(1);});
    threaded.Reclaim(true,[](CommandQueue::Call&){std::this_thread::yield();});browser.join();
    Check(!threaded.PendingCount());++checks;
    CommandQueue failed;auto& failure=failed.Enqueue("commands","[]",data,wait);failure.ready.store(2);
    bool threw=false;try{failed.Reclaim(true,wait);}catch(const std::runtime_error&){threw=true;}
    Check(threw && failed.PendingCount()==1 && failed.PendingBytes()==4);++checks;
    std::cout<<"{\"passed\":true,\"checks\":"<<checks<<"}\n";
}
