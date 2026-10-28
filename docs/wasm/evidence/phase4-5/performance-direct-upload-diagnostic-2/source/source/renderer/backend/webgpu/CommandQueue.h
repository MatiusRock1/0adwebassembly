/* Copyright (C) 2026 Wildfire Games.
 * This file is part of 0 A.D., licensed under GPL-2.0-or-later.
 */
#pragma once
#include <algorithm>
#include <atomic>
#include <cstdint>
#include <deque>
#include <memory>
#include <span>
#include <stdexcept>
#include <string>
#include <vector>

namespace Renderer::Backend::WebGPU
{
// The renderer thread owns the queue. The browser consumes immutable payloads
// and acknowledges each call through ready; only acknowledged calls are freed.
class CommandQueue
{
public:
    struct Call
    {
        alignas(4) std::atomic<int> ready{0};
        std::string method, args;
        std::vector<uint8_t> data;
        uint32_t sequence;
    };
    explicit CommandQueue(size_t maxCalls = 64, size_t maxBytes = 64*1024*1024)
        : m_MaxCalls(maxCalls), m_MaxBytes(maxBytes) {}

    template<class Wait> void Reclaim(bool blocking, Wait wait)
    {
        while (!m_Calls.empty())
        {
            auto& call = *m_Calls.front();
            while (!call.ready.load())
            {
                if (!blocking) return;
                wait(call);
            }
            if (call.ready.load() != 1)
                throw std::runtime_error("WebGPU asynchronous command failed");
            m_Bytes -= call.data.size();
            m_Calls.pop_front();
        }
    }

    template<class Wait> Call& Enqueue(const std::string& method, const std::string& args,
        std::span<const uint8_t> data, Wait wait)
    {
        Reclaim(false,wait);
        // A single oversized upload may exceed the byte budget; another call
        // cannot follow it until the browser has consumed it.
        if (m_Calls.size() >= m_MaxCalls || m_Bytes > m_MaxBytes ||
            data.size() > m_MaxBytes - std::min(m_Bytes,m_MaxBytes))
            Reclaim(true,wait);
        auto call = std::make_unique<Call>();
        call->method = method; call->args = args;
        if (!data.empty()) call->data.assign(data.begin(),data.end());
        call->sequence = ++m_Sequence;
        m_Bytes += data.size();
        m_Calls.push_back(std::move(call));
        return *m_Calls.back();
    }
    size_t PendingCount() const { return m_Calls.size(); }
    size_t PendingBytes() const { return m_Bytes; }
private:
    std::deque<std::unique_ptr<Call>> m_Calls;
    size_t m_MaxCalls, m_MaxBytes, m_Bytes = 0;
    uint32_t m_Sequence = 0;
};
}
