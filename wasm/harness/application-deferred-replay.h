#pragma once
#include <algorithm>
#include <ostream>
#include <utility>
#include <vector>

namespace WasmApplication
{
// Owned by the original engine thread. Formatting and appending replay records
// stay at their original simulation points. Only the explicit per-turn flush
// moves behind CPU frame recording, before posting that frame's GPU commands.
// Every request is retained, including multiple catch-up turns in one frame.
class DeferredReplayFlushes
{
public:
    bool enabled = false;

    void Schedule(std::ostream& stream)
    {
        if (!enabled) { stream.flush(); return; }
        // Bound pending pointers even if a caller runs without rendering.
        if (m_Pending.size() == 64) Drain();
        m_Pending.push_back(&stream);
    }

    void Drain()
    {
        std::vector<std::ostream*> pending;
        pending.swap(m_Pending);
        for (auto* stream : pending) stream->flush();
    }

    // A logger must finish its queued requests before deleting its stream or
    // exposing completed replay metadata. Other loggers retain their requests.
    void DrainStream(std::ostream& stream)
    {
        const auto count = std::count(m_Pending.begin(), m_Pending.end(), &stream);
        std::erase(m_Pending, &stream);
        for (auto i = count; i > 0; --i) stream.flush();
    }

    size_t PendingCount() const { return m_Pending.size(); }

private:
    std::vector<std::ostream*> m_Pending;
};

inline DeferredReplayFlushes replayFlushes;
}
