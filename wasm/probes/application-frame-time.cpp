#include "application-frame-time.h"
#include <cmath>
#include <cstdlib>
#include <iostream>

int main()
{
    unsigned checks=0;
    auto check=[&](bool result,const char* message) {
        if(!result){std::cerr<<message<<'\n';std::exit(1);}++checks;
    };
    WasmApplication::FrameTime time;
    check(std::abs(time.Advance(10,0)-1.0/60)<1e-8,"first frame must be positive");
    check(std::abs(time.Advance(10.02,0)-.02)<1e-8,"ordinary elapsed delta");
    check(std::abs(time.Advance(10.82,0)-.8)<1e-7,"long frame must not discard elapsed time");
    time.Reset();time.Advance(0,0);
    double now=0,total=0;
    for(unsigned i=0;i<1000;++i)
        for(double delta:{.016,.033,.7,.016,.12,.017}){now+=delta;total+=time.Advance(now,0);}
    check(std::abs(now-total)<.0001,"mixed fast/slow frames must conserve elapsed time");
    time.Reset();double fixed=0;
    for(unsigned i=0;i<120;++i)fixed+=time.Advance(i*.8,60);
    check(std::abs(fixed-2)<1e-6,"original functional fixed-frequency option");
    time.Reset();check(time.Advance(10000,0)<.017,"restart must not inherit the old timestamp");
    // Present pacing: a frame advances by its display signal, not by its start.
    time.Reset();time.SetNominal(50);time.Advance(1,0);
    time.SetNominal(50+1.0/30);
    check(std::abs(time.Advance(1.004,0)-1.0/30)<1e-7,"an early paced frame advances one display interval");
    check(std::abs(time.Advance(1.05,0)-.046)<1e-7,"a frame without a signal uses the real elapsed time");
    time.SetNominal(60);
    check(std::abs(time.Advance(1.08,0)-.03)<1e-7,"a signal after an unpaced frame has nothing to compare with");
    time.SetNominal(60+1.0/30);
    check(std::abs(time.Advance(1.09,0)-1.0/30)<1e-7,"pacing resumes on the next signal");
    time.SetNominal(70);time.Reset();time.Advance(2,0);time.SetNominal(80);
    check(std::abs(time.Advance(2.03,0)-.03)<1e-7,"reset discards a pending signal");
    time.SetNominal(80+1.0/30);
    check(std::abs(time.Advance(2.05,60)-1.0/60)<1e-7,"the fixed-frequency option still wins");
    time.Reset();time.SetNominal(0);time.Advance(0,0);
    double signal=0,start=0,paced=0;
    for(unsigned i=0;i<600;++i)
    {
        // Early turn frames and late ones; the signals keep a 30 FPS cadence
        // with one late present every tenth frame.
        signal+=i%10==9 ? 1.0/20 : 1.0/30;start+=i%6==0 ? .004 : .041;
        time.SetNominal(signal);paced+=time.Advance(start,0);
    }
    check(std::abs(paced-signal)<1e-6,"paced frames must conserve display time");
    std::cout<<"{\"passed\":true,\"checks\":"<<checks<<",\"mixedElapsedSeconds\":"<<total<<"}\n";
}
