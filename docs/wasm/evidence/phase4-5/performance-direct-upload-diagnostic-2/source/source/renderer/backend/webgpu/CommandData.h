/* Copyright (C) 2026 Wildfire Games. GPL-2.0-or-later. */
#pragma once
#include <algorithm>
#include <cstdint>
#include <cstring>
#include <limits>
#include <span>
#include <stdexcept>
#include <vector>

namespace Renderer::Backend::WebGPU
{
struct BufferedUpload
{
    uint32_t bufferOffset, byteSize, dataOffset;
};

// Copy aligned neighbors directly from the original buffer mirror into the
// owned command packet. No intermediate zero-filled upload vector is needed.
inline BufferedUpload AppendUploadBytes(std::vector<uint8_t>& data,
    std::span<const uint8_t> mirror, uint32_t offset, uint32_t size)
{
    if (offset > mirror.size() || size > mirror.size() - offset)
        throw std::out_of_range("WebGPU buffer upload exceeds its mirror");
    const uint64_t start = uint64_t(offset) & ~uint64_t(3);
    const uint64_t end = (uint64_t(offset) + size + 3) & ~uint64_t(3);
    const uint64_t payload = (uint64_t(data.size()) + 3) & ~uint64_t(3);
    const uint64_t count = end - start;
    if (end > std::numeric_limits<uint32_t>::max() ||
        payload > std::numeric_limits<uint32_t>::max() - count)
        throw std::length_error("WebGPU buffer upload exceeds packet offsets");
    data.resize(payload + count, 0);
    const size_t available = std::min<uint64_t>(end, mirror.size()) - start;
    if (available) std::memcpy(data.data() + payload, mirror.data() + start, available);
    return {uint32_t(start), uint32_t(count), uint32_t(payload)};
}
}
