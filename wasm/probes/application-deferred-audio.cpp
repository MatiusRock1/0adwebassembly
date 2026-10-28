#include "application-deferred-audio.h"
#include <iostream>
#include <stdexcept>

using namespace WasmApplication;
unsigned count=0;
void Tick() { ++count; }
void Check(bool ok) { if (!ok) throw std::runtime_error("Deferred audio probe failed"); }
void Reentrant() { ++count;RunDeferredAudioIdle(); }
int main()
{
    unsigned checks=0;
    ScheduleAudioIdle(Tick);Check(count==1 && !pendingAudioIdle);++checks;
    deferAudioIdle=true;ScheduleAudioIdle(Tick);Check(count==1 && pendingAudioIdle);++checks;
    RunDeferredAudioIdle();RunDeferredAudioIdle();Check(count==2 && !pendingAudioIdle);++checks;
    ScheduleAudioIdle(Tick);ScheduleAudioIdle(Tick);Check(count==3 && pendingAudioIdle);RunDeferredAudioIdle();Check(count==4);++checks;
    ScheduleAudioIdle(Reentrant);RunDeferredAudioIdle();Check(count==5 && !pendingAudioIdle);++checks;
    deferAudioIdle=false;ScheduleAudioIdle(Tick);RunDeferredAudioIdle();Check(count==6 && !pendingAudioIdle);++checks;
    std::cout<<"{\"passed\":true,\"checks\":"<<checks<<"}\n";
}
