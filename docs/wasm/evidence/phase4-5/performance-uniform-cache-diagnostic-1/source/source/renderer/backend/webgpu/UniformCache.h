/* Copyright (C) 2026 Wildfire Games. GPL-2.0-or-later. */
#pragma once
#include <cstdint>
#include <cstring>
#include <span>
#include <unordered_map>
#include <vector>

namespace Renderer::Backend::WebGPU
{
// Only omit identical writes within one indivisible command packet. Another
// context can change shader state between packets, so Clear is a state fence.
class UniformCache
{
public:
    explicit UniformCache(size_t budget = 2*1024*1024) : m_Budget(budget) {}
    bool Update(int32_t slot, std::span<const uint8_t> bytes)
    {
        auto found = m_Values.find(slot);
        if (found != m_Values.end() && found->second.size() == bytes.size() &&
            (bytes.empty() || std::memcmp(found->second.data(), bytes.data(), bytes.size()) == 0))
            return false;
        const size_t previous = found == m_Values.end() ? 0 : found->second.size();
        if (bytes.size() > m_Budget)
        {
            // A forwarded oversized write invalidates its old cached value.
            if (found != m_Values.end()) { m_Bytes -= previous; m_Values.erase(found); }
            return true;
        }
        if (bytes.size() > m_Budget - (m_Bytes - previous)) Clear();
        auto& value = m_Values[slot];
        m_Bytes -= value.size();
        value.assign(bytes.begin(), bytes.end());
        m_Bytes += value.size();
        return true;
    }
    void Clear() { m_Values.clear(); m_Bytes = 0; }
    size_t Bytes() const { return m_Bytes; }
private:
    const size_t m_Budget;
    size_t m_Bytes = 0;
    std::unordered_map<int32_t, std::vector<uint8_t>> m_Values;
};
}
