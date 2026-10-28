#pragma once

namespace WasmApplication
{
// Browser display/worker delays are real elapsed time, not a frame-rate
// estimate. Keep the original explicit fixed-frequency option for functional
// image comparisons; performance runners forbid that option.
class FrameTime
{
public:
    float Advance(double now,int fixedFrequency)
    {
        // A paced frame (SetNominal) advances by the display time between its
        // own and the previous frame's signal, so a frame that starts early
        // still moves the scene by one display interval. Without a signal for
        // both frames, it advances by the real elapsed time.
        const double elapsed=!m_Started ? 1.0/60.0 :
            m_HasNominal && m_PreviousHasNominal ? m_Nominal-m_PreviousNominal : now-m_Previous;
        m_Previous=now;
        m_PreviousNominal=m_Nominal;m_PreviousHasNominal=m_HasNominal;m_HasNominal=false;
        m_Started=true;
        return static_cast<float>(fixedFrequency>0 ? 1.0/fixedFrequency : elapsed>0 ? elapsed : 1.0/60.0);
    }
    // Display signal time, in seconds of a fixed clock, of the frame that the
    // next Advance starts. Consumed by that Advance.
    void SetNominal(double seconds) { m_Nominal=seconds;m_HasNominal=true; }
    void Reset() { m_Started=false;m_Previous=0;m_HasNominal=m_PreviousHasNominal=false; }
private:
    bool m_Started=false;
    double m_Previous=0;
    bool m_HasNominal=false,m_PreviousHasNominal=false;
    double m_Nominal=0,m_PreviousNominal=0;
};
inline FrameTime frameTime;
}
