/* SPDX-License-Identifier: GPL-2.0-or-later */
#pragma once
#include <cmath>
#include <cstdint>
#include <span>

namespace AIMapKernels
{
// Preconditions: square byte map; integer interior centre; the original
// per-row pattern has been validated and is bounded by radius.
inline int Obstruction(std::span<const uint8_t> map, int width, int x, int y,
    int radius, std::span<const double> pattern)
{
    for (int dy = 0; dy <= radius; ++dy)
    {
        const int dxmax = pattern[dy];
        const int xp = x + (y+dy)*width, xm = x + (y-dy)*width;
        for (int dx = 0; dx <= dxmax; ++dx)
        {
            if (!map[xp+dx]) return xp+dx;
            if (!map[xm+dx]) return xm+dx;
            if (!map[xp-dx]) return xp-dx;
            if (!map[xm-dx]) return xm-dx;
        }
    }
    return -1;
}
// Match the original JS expression order, clamp, and Uint8Array conversion.
// No fast-math: every intermediate is a binary64 value.
inline void AddInfluence(std::span<uint8_t> map, int width, int x0, int x1,
    int y0, int y1, double cx, double cy, double distance, double strength,
    double maximum, int type)
{
    const double distance2 = distance * distance;
    const double scale = type == 0 ? strength / distance : strength / distance2;
    for (int y = y0; y < y1; ++y)
    {
        const double dy = y - cy, dy2 = dy * dy;
        for (int x = x0; x < x1; ++x)
        {
            const double dx = x - cx, r2 = dx * dx + dy2;
            if (r2 >= distance2) continue;
            const auto index = x + y * width;
            double value = type == 0 ? map[index] + scale * (distance - std::sqrt(r2)) :
                type == 1 ? map[index] + scale * (distance2 - r2) : map[index] + strength;
            value = value < 0 ? 0 : value > maximum ? maximum : value;
            // Preconditions limit maximum to 255, so this also implements
            // ToUint8 for the finite values admitted by the wrapper.
            map[index] = static_cast<uint8_t>(value);
        }
    }
}

inline constexpr char Install[] = R"AIJS(
globalThis.__installAIMapKernels = function(module) {
    const p = module.InfoMap.prototype, original = p.addInfluence;
    const set = p.set, runLoop = p.runLoop;
    const originalObstruction = p.isObstructedTile;
    p.addInfluence = function(cx, cy, distance, strength, type = 'linear') {
        const amount = strength ? strength : distance;
        if (this.set === set && this.runLoop === runLoop &&
            Number.isInteger(this.width) && Number.isInteger(this.height) &&
            this.width * this.height === this.map.length &&
            [cx, cy, distance, amount, this.maxVal].every(v => typeof v === 'number') &&
            Engine.AIMapAddInfluence(this.map, this.width, cx, cy, distance,
                amount, this.maxVal, type == 'linear' ? 0 : type == 'quadratic' ? 1 : 2))
            return;
        return original.call(this, cx, cy, distance, strength, type);
    };
    p.isObstructedTile = function(x, y, radius) {
        const w = this.width;
        if (!Number.isInteger(w) || !Number.isInteger(x) || !Number.isInteger(y) ||
            !Number.isInteger(radius) || radius < 0 || radius > 32768 ||
            this.height !== w || !(this.map instanceof Uint8Array) || this.map.length !== w*w ||
            x < radius || x >= w-radius || y < radius || y >= w-radius || this.map[x+y*w] == 0)
            return originalObstruction.call(this, x, y, radius);
        if (!this.pattern || this.pattern[0] != radius) {
            this.pattern = [radius];
            const r2 = radius * radius;
            for (let i = 1; i <= radius; ++i)
                this.pattern.push(Math.floor(Math.sqrt(r2-(i-0.5)*(i-0.5))+0.5));
        }
        const result = Engine.AIMapObstruction(this.map,w,x,y,radius,this.pattern);
        if (result === -2) return originalObstruction.call(this,x,y,radius);
        return result < 0 ? null : {x:result%w,y:Math.floor(result/w)};
    };
};
)AIJS";
}
