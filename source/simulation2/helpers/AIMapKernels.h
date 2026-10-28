/* SPDX-License-Identifier: GPL-2.0-or-later */
#pragma once
#include <cmath>
#include <cstdint>
#include <atomic>
#include <span>
#include <vector>

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

// Usage counters, read by diagnostics through Phase45AIKernelStats.
inline std::atomic<unsigned> bestTileCalls{0}, bestTileFallbacks{0}, bestTileVerified{0}, obstructionCalls{0};
// Verified calls per kernel: 0 findBestTile, 1 addEnt, 2 updateTerritories,
// 3 createObstructionMap's territory loop.
inline std::atomic<unsigned> verifiedByKind[4]{};

// petra/mapModule.js createObstructionMap's territory loop, guarded in the module
// source (scriptinterface/ModuleSourceKernels.h). Preconditions, checked by the
// wrapper: integer ratio >= 1 and widths >= 1, tiles as long as passability, an
// ally entry (1 no, 2 yes) for every tile owner other than playerID. Indices out
// of range have no effect, as the original's typed array accesses.
template<typename Passability, typename Access>
inline void ObstructionTiles(std::span<uint8_t> tiles, std::span<const uint8_t> territory, int territoryWidth,
    std::span<const Passability> passability, int passabilityWidth, std::span<const Access> access,
    bool checkAccess, double accessIndex, int32_t obstructionMask, int ratio, int32_t playerID,
    int32_t playerMask, int32_t blinkingMask, bool buildOwn, bool buildAlly, bool buildNeutral,
    bool buildEnemy, std::span<const uint8_t> allies)
{
    for (size_t k = 0; k < territory.size(); ++k)
    {
        const int32_t tilePlayer = int32_t(territory[k]) & playerMask;
        const bool isConnected = (int32_t(territory[k]) & blinkingMask) == 0;
        if (tilePlayer == playerID)
        {
            if (!buildOwn || (!buildNeutral && !isConnected))
                continue;
        }
        else if (allies[tilePlayer] == 2)
        {
            if (!buildAlly || (!buildNeutral && !isConnected))
                continue;
        }
        else if (tilePlayer == 0)
        {
            if (!buildNeutral)
                continue;
        }
        else if (!buildEnemy)
            continue;

        const size_t x = size_t(ratio) * (k % size_t(territoryWidth));
        const size_t y = size_t(ratio) * (k / size_t(territoryWidth));
        for (int ix = 0; ix < ratio; ++ix)
            for (int iy = 0; iy < ratio; ++iy)
            {
                const size_t i = x + ix + (y + iy) * size_t(passabilityWidth);
                // passMap[i] is undefined out of range, and never equals a number.
                if (checkAccess && (i >= access.size() || double(access[i]) != accessIndex))
                    continue;
                if (i >= passability.size())
                    continue;
                if (!(int32_t(passability[i]) & obstructionMask))
                    tiles[i] = 255;
            }
    }
}

// Installs __aiObstructionTiles, called by the guard; returns false whenever the
// original loop must run instead.
inline constexpr char ObstructionInstall[] = R"AIJS(
(function() {
    const hash = text => {
        let h = 0x811c9dc5;
        for (let i = 0; i < text.length; ++i)
            h = Math.imul(h ^ text.charCodeAt(i), 0x01000193) >>> 0;
        return h;
    };
    const allyMethods = new WeakMap();
    const integer = (v, lo, hi) => typeof v === "number" && Number.isInteger(v) && v >= lo && v <= hi;
    const shorts = a => a instanceof Uint16Array || a instanceof Uint8Array;
    // The original loop over the guard's arguments, for verification only.
    const reference = (obstructionTiles, territoryMap, passabilityMap, passMap, obstructionMask, ratio, notShore,
        accessIndex, PlayerID, TERRITORY_PLAYER_MASK, TERRITORY_BLINKING_MASK, buildOwn, buildAlly, buildNeutral,
        buildEnemy, gameState) => {
        for (let k = 0; k < territoryMap.data.length; ++k)
        {
            const tilePlayer = territoryMap.data[k] & TERRITORY_PLAYER_MASK;
            const isConnected = (territoryMap.data[k] & TERRITORY_BLINKING_MASK) == 0;
            if (tilePlayer === PlayerID)
            {
                if (!buildOwn || !buildNeutral && !isConnected)
                    continue;
            }
            else if (gameState.isPlayerMutualAlly(tilePlayer))
            {
                if (!buildAlly || !buildNeutral && !isConnected)
                    continue;
            }
            else if (tilePlayer === 0)
            {
                if (!buildNeutral)
                    continue;
            }
            else
            {
                if (!buildEnemy)
                    continue;
            }

            const x = ratio * (k % territoryMap.width);
            const y = ratio * Math.floor(k / territoryMap.width);
            for (let ix = 0; ix < ratio; ++ix)
            {
                for (let iy = 0; iy < ratio; ++iy)
                {
                    const i = x + ix + (y + iy)*passabilityMap.width;
                    if (notShore && accessIndex && accessIndex !== passMap[i])
                        continue;
                    if (!(passabilityMap.data[i] & obstructionMask))
                        obstructionTiles[i] = 255;
                }
            }
        }
    };
    globalThis.__aiObstructionTiles = function(obstructionTiles, territoryMap, passabilityMap, passMap,
        obstructionMask, ratio, notShore, accessIndex, playerID, playerMask, blinkingMask, buildOwn, buildAlly,
        buildNeutral, buildEnemy, gameState) {
        const isAlly = gameState.isPlayerMutualAlly;
        if (typeof isAlly !== "function")
            return false;
        let unchanged = allyMethods.get(isAlly);
        if (unchanged === undefined)
            allyMethods.set(isAlly, unchanged = hash(isAlly.toString()) === 0x1265063f);
        if (!unchanged)
            return false;
        const tData = territoryMap.data, pData = passabilityMap.data;
        if (!(tData instanceof Uint8Array) || !shorts(pData) || !(obstructionTiles instanceof Uint8Array) ||
            obstructionTiles.length !== pData.length)
            return false;
        const tWidth = territoryMap.width, pWidth = passabilityMap.width;
        if (!integer(tWidth, 1, 65536) || !integer(pWidth, 1, 65536) || !integer(ratio, 1, 64) ||
            !integer(playerID, -2147483648, 2147483647) || typeof playerMask !== "number" ||
            typeof blinkingMask !== "number" || (obstructionMask !== undefined && typeof obstructionMask !== "number"))
            return false;
        const checkAccess = !!(notShore && accessIndex);
        if (checkAccess && (typeof accessIndex !== "number" || !shorts(passMap)))
            return false;
        const mask = playerMask | 0, blink = blinkingMask | 0;
        // isPlayerMutualAlly is a pure lookup: one call per owner value, in the
        // order the original first reaches it.
        const allies = new Uint8Array(256);
        for (let k = 0; k < tData.length; ++k)
        {
            const tilePlayer = tData[k] & mask;
            if (tilePlayer === playerID || allies[tilePlayer])
                continue;
            allies[tilePlayer] = gameState.isPlayerMutualAlly(tilePlayer) ? 2 : 1;
        }
        const verify = !!globalThis.__aiKernelVerify;
        const target = verify ? new Uint8Array(obstructionTiles.length) : obstructionTiles;
        const flags = (buildOwn ? 1 : 0) | (buildAlly ? 2 : 0) | (buildNeutral ? 4 : 0) | (buildEnemy ? 8 : 0);
        if (!Engine.AIObstructionTiles(target, tData, tWidth, pData, pWidth, checkAccess ? passMap : pData,
            checkAccess, checkAccess ? accessIndex : 0, obstructionMask | 0, ratio, playerID, mask, blink, flags, allies))
            return false;
        if (verify)
        {
            reference(obstructionTiles, territoryMap, passabilityMap, passMap, obstructionMask, ratio, notShore,
                accessIndex, playerID, playerMask, blinkingMask, buildOwn, buildAlly, buildNeutral, buildEnemy, gameState);
            for (let i = 0; i < target.length; ++i)
                if (target[i] !== obstructionTiles[i])
                    throw new Error("AIObstructionTiles mismatch at " + i);
            Engine.AIMapKernelVerified(3);
        }
        return true;
    };
})();
)AIJS";

struct BestTileResult
{
    bool found = false;
    int idx = 0, val = 0;
    // The original isObstructedTile builds obstruction.pattern on its first
    // in-bounds call with a non-zero centre; the wrapper reproduces that.
    bool patternUsed = false;
};

// InfoMap.findBestTile with getNonObstructedTile/isObstructedTile inlined, in the
// original visiting order. Preconditions: byte maps, square obstruction map of
// width ow, integer ratio >= 1 and radius >= 0, map.size() == width*height.
inline BestTileResult BestTile(std::span<const uint8_t> map, int width, int ratio,
    std::span<const uint8_t> obstruction, int ow, int radius)
{
    std::vector<int> pattern(radius + 1);
    pattern[0] = radius;
    const double r2 = double(radius) * radius;
    for (int i = 1; i <= radius; ++i)
        pattern[i] = int(std::floor(std::sqrt(r2 - (i - 0.5) * (i - 0.5)) + 0.5));
    BestTileResult result;
    int bestVal = 0;
    for (std::size_t j = 0; j < map.size(); ++j)
    {
        if (map[j] <= bestVal)
            continue;
        const int ix = int(j % width) * ratio, iy = int(j / width) * ratio;
        bool hasLast = false;
        int lastX = 0, lastY = 0, found = -1;
        for (int kx = ix; kx < ix + ratio && found < 0; ++kx)
        {
            if (kx < radius || kx >= ow - radius)
                continue;
            for (int ky = iy; ky < iy + ratio; ++ky)
            {
                if (ky < radius || ky >= ow - radius)
                    continue;
                if (hasLast && double(kx - lastX) * (kx - lastX) + double(ky - lastY) * (ky - lastY) < r2)
                    continue;
                // isObstructedTile: the bounds checks above already hold.
                hasLast = true;
                if (!obstruction[kx + ky * ow]) { lastX = kx; lastY = ky; continue; }
                result.patternUsed = true;
                bool obstructed = false;
                for (int dy = 0; dy <= radius && !obstructed; ++dy)
                {
                    const int dxmax = pattern[dy];
                    const int xp = kx + (ky + dy) * ow, xm = kx + (ky - dy) * ow;
                    for (int dx = 0; dx <= dxmax; ++dx)
                    {
                        if (!obstruction[xp + dx]) { lastX = kx + dx; lastY = ky + dy; obstructed = true; break; }
                        if (!obstruction[xm + dx]) { lastX = kx + dx; lastY = ky - dy; obstructed = true; break; }
                        if (!obstruction[xp - dx]) { lastX = kx - dx; lastY = ky + dy; obstructed = true; break; }
                        if (!obstruction[xm - dx]) { lastX = kx - dx; lastY = ky - dy; obstructed = true; break; }
                    }
                }
                if (!obstructed) { found = kx + ky * ow; break; }
            }
        }
        if (found < 0)
            continue;
        bestVal = map[j];
        result.found = true;
        result.idx = found;
        result.val = bestVal;
    }
    return result;
}

struct TerritoryMasks
{
    int outside, fullFrontier, narrowFrontier, largeFrontier;
};

// Petra Headquarters.updateTerritories loop. Writes the frontier bits of border
// in the original order and returns, in increasing index order, the indices whose
// base call has an effect: 2*j for removeBaseFromTerritoryIndex (base != 0) and
// 2*j+1 for addTerritoryIndexToBase (base == 0). Calls on other indices return
// without effect in the original. ownerOf maps a territory byte to its owner, as
// probed from getOwnerIndex; offsets are the original Math.round results.
// Preconditions: square maps of width*width bytes.
inline std::vector<int> UpdateTerritories(std::span<const uint8_t> territory, std::span<const uint8_t> ownerOf,
    std::span<uint8_t> border, std::span<const uint8_t> bases, int width, std::span<const int32_t> small,
    std::span<const int32_t> large, TerritoryMasks masks, int player, bool alliedVictory, std::span<const uint8_t> ally)
{
    std::vector<int> ops{1};
    const auto isFoe = [&](int index) {
        const int owner = ownerOf[territory[index]];
        return owner != player && !(alliedVictory && owner < int(ally.size()) && ally[owner]);
    };
    const int length = width * width;
    for (int j = 0; j < length; ++j)
    {
        if (border[j] & masks.outside)
            continue;
        if (border[j] & masks.fullFrontier)
            border[j] &= uint8_t(~masks.fullFrontier);
        if (ownerOf[territory[j]] != player)
        {
            if (bases[j] != 0)
                ops.push_back(2 * j);
            continue;
        }
        const int ix = j % width, iz = j / width;
        bool onFrontier = false;
        for (int a = 0; a < 8; ++a)
        {
            int jx = ix + small[2 * a];
            if (jx < 0 || jx >= width) continue;
            int jz = iz + small[2 * a + 1];
            if (jz < 0 || jz >= width) continue;
            if (border[jx + width * jz] & masks.outside) continue;
            if (isFoe(jx + width * jz))
            {
                border[j] |= uint8_t(masks.narrowFrontier);
                break;
            }
            jx = ix + large[2 * a];
            if (jx < 0 || jx >= width) continue;
            jz = iz + large[2 * a + 1];
            if (jz < 0 || jz >= width) continue;
            if (border[jx + width * jz] & masks.outside) continue;
            if (isFoe(jx + width * jz))
                onFrontier = true;
        }
        if (onFrontier && !(border[j] & masks.narrowFrontier))
            border[j] |= uint8_t(masks.largeFrontier);
        if (bases[j] == 0)
            ops.push_back(2 * j + 1);
    }
    return ops;
}

// Installed after the engine loads the Petra entry module, so that no Petra module
// is evaluated earlier than in the original order.
inline constexpr char PetraInstall[] = R"AIJS(
globalThis.__installPetraKernels = function(hqModule, basesModule, masks) {
    const H = hqModule.Headquarters.prototype;
    if (Object.hasOwn(H, '__wasmTerritoryKernel')) return;
    Object.defineProperty(H, '__wasmTerritoryKernel', { value: true });
    const B = basesModule.BasesManager.prototype;
    const originalUpdate = H.updateTerritories, removeBase = B.removeBaseFromTerritoryIndex, addBase = B.addTerritoryIndexToBase;
    const ownerSource = 'function(p) { return this.map[p] & TERRITORY_PLAYER_MASK; }';
    const probe = { map: Uint8Array.from({ length: 256 }, (_, i) => i) };
    const around = [ [-0.7, 0.7], [0, 1], [0.7, 0.7], [1, 0], [0.7, -0.7], [0, -1], [-0.7, -0.7], [-1, 0] ];
    const prepare = function(hq, gameState) {
        const tm = hq.territoryMap, bm = hq.basesManager;
        if (!tm || String(tm.getOwnerIndex) !== ownerSource || !bm || !hq.borderMap || !bm.basesMap ||
            bm.removeBaseFromTerritoryIndex !== removeBase || bm.addTerritoryIndexToBase !== addBase ||
            tm.width !== tm.height || tm.length !== tm.width * tm.height ||
            ![masks.outside, masks.fullFrontier, masks.narrowFrontier, masks.largeFrontier, PlayerID].every(Number.isInteger))
            return null;
        const ownerOf = new Uint8Array(256);
        for (let v = 0; v < 256; ++v) {
            const owner = tm.getOwnerIndex.call(probe, v);
            if (!Number.isInteger(owner) || owner < 0 || owner > 255) return null;
            ownerOf[v] = owner;
        }
        const alliedVictory = gameState.getAlliedVictory();
        const ally = new Uint8Array(256);
        if (alliedVictory)
            for (let p = 0; p < 256; ++p) ally[p] = gameState.isPlayerAlly(p) ? 1 : 0;
        const insideSmall = Math.round(45 / tm.cellSize), insideLarge = Math.round(80 / tm.cellSize);
        const offsets = [];
        for (const a of around) offsets.push(Math.round(insideSmall*a[0]), Math.round(insideSmall*a[1]));
        for (const a of around) offsets.push(Math.round(insideLarge*a[0]), Math.round(insideLarge*a[1]));
        const values = [tm.width, masks.outside, masks.fullFrontier, masks.narrowFrontier, masks.largeFrontier,
            PlayerID, alliedVictory ? 1 : 0, ...offsets];
        if (!values.every(v => Number.isInteger(v) && Math.abs(v) < 2**31)) return null;
        return { tm, bm, ownerOf, ally, params: Int32Array.from(values) };
    };
    H.updateTerritories = function(gameState) {
        const passabilityMap = gameState.getPassabilityMap();
        const p = prepare(this, gameState);
        if (globalThis.__aiKernelVerify && p) {
            // Diagnostic: kernel on a copy, then the original on the real state with
            // its effective base calls recorded; both must match.
            const border = this.borderMap.map.slice();
            const ops = Engine.AIMapUpdateTerritories(p.tm.map, p.ownerOf, border, p.bm.basesMap.map, p.params, p.ally);
            const calls = [];
            p.bm.removeBaseFromTerritoryIndex = function(j) { if (this.basesMap.map[j] != 0) calls.push(2*j); return removeBase.call(this, j); };
            p.bm.addTerritoryIndexToBase = function(gs, j, pm) { if (this.baseAtIndex(j) == 0) calls.push(2*j+1); return addBase.call(this, gs, j, pm); };
            try { originalUpdate.call(this, gameState); }
            finally { delete p.bm.removeBaseFromTerritoryIndex; delete p.bm.addTerritoryIndexToBase; }
            if (!ops.length || ops.length - 1 !== calls.length || calls.some((c, i) => c !== ops[i + 1]) ||
                border.some((v, i) => v !== this.borderMap.map[i]))
                throw new Error('Headquarters.updateTerritories kernel mismatch');
            Engine.AIMapKernelVerified(2);
            return;
        }
        const ops = p && Engine.AIMapUpdateTerritories(p.tm.map, p.ownerOf, this.borderMap.map, p.bm.basesMap.map, p.params, p.ally);
        if (!ops || !ops.length) {
            if (globalThis.__aiKernelVerify) Engine.AIMapKernelFallback();
            return originalUpdate.call(this, gameState);
        }
        let expansion = 0;
        for (let k = 1; k < ops.length; ++k) {
            const j = ops[k] >> 1;
            if (ops[k] & 1) {
                if (this.basesManager.addTerritoryIndexToBase(gameState, j, passabilityMap))
                    expansion++;
            }
            else
                this.basesManager.removeBaseFromTerritoryIndex(j);
        }
        // The rest is the original method unchanged.
        if (!expansion)
            return;
        this.buildManager.resetMissingRoom(gameState);
        const cellArea = this.territoryMap.cellSize * this.territoryMap.cellSize;
        if (expansion * cellArea > 960)
            this.tradeManager.routeProspection = true;
    };
};
)AIJS";

inline constexpr char Install[] = R"AIJS(
globalThis.__installAIMapKernels = function(module, collections) {
    // EntityCollection.addEnt re-sorts the whole map by id on every insertion.
    // When the map is already strictly sorted by numeric id (key === value.id()),
    // inserting at the right position yields the same order as that stable sort.
    const C = collections.EntityCollection.prototype, originalAddEnt = C.addEnt;
    C.addEnt = function(ent) {
        const id = ent.id();
        const entities = this._entities;
        if (entities.has(id))
            return false;
        if (Number.isFinite(id)) {
            let last = -Infinity, sorted = true, before = 0;
            for (const [key, e] of entities) {
                const eid = e.id();
                if (key !== eid || !Number.isFinite(eid) || !(eid > last)) { sorted = false; break; }
                last = eid;
                if (eid < id) ++before;
            }
            if (sorted) {
                const expected = globalThis.__aiKernelVerify &&
                    Array.from(entities.values()).concat([ent]).sort((a, b) => a.id() - b.id());
                if (before === entities.size) {
                    entities.set(id, ent);
                } else {
                    const ordered = Array.from(entities.values());
                    ordered.splice(before, 0, ent);
                    entities.clear();
                    for (const e of ordered) entities.set(e.id(), e);
                }
                if (expected) {
                    const actual = Array.from(entities);
                    if (actual.length !== expected.length || actual.some(([k, e], i) => e !== expected[i] || k !== expected[i].id()))
                        throw new Error('EntityCollection.addEnt order mismatch');
                    Engine.AIMapKernelVerified(1);
                }
                return true;
            }
        }
        if (globalThis.__aiKernelVerify) Engine.AIMapKernelFallback();
        return originalAddEnt.call(this, ent);
    };
    const p = module.InfoMap.prototype, original = p.addInfluence;
    const set = p.set, runLoop = p.runLoop;
    const originalObstruction = p.isObstructedTile;
    // Type, integer and size checks run natively on the unconverted values;
    // this wrapper runs in the portable interpreter on every call.
    p.addInfluence = function(cx, cy, distance, strength, type = 'linear') {
        if (this.set === set && this.runLoop === runLoop &&
            Engine.AIMapAddInfluence(this.map, this.width, this.height, cx, cy, distance,
                strength ? strength : distance, this.maxVal,
                type == 'linear' ? 0 : type == 'quadratic' ? 1 : 2))
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
    const originalBestTile = p.findBestTile, nonObstructed = p.getNonObstructedTile, obstructed = p.isObstructedTile;
    p.findBestTile = function(radius, obstruction) {
        if (this.getNonObstructedTile === nonObstructed && obstruction && obstruction.isObstructedTile === obstructed &&
            this.length === this.map.length)
        {
            const r = Engine.AIMapBestTile(this.map, this.width, this.height, this.cellSize / obstruction.cellSize,
                obstruction.map, obstruction.width, radius);
            if (r.length === 4) {
                let slow, slowPattern;
                if (globalThis.__aiKernelVerify) {
                    // Diagnostic: run the original on the same state first, then restore it.
                    const before = obstruction.pattern;
                    slow = originalBestTile.call(this, radius, obstruction);
                    slowPattern = JSON.stringify(obstruction.pattern);
                    obstruction.pattern = before;
                }
                // Same pattern the original isObstructedTile would have left.
                if (r[3] && (!obstruction.pattern || obstruction.pattern[0] != radius)) {
                    obstruction.pattern = [radius];
                    const r2 = radius * radius;
                    for (let i = 1; i <= radius; ++i)
                        obstruction.pattern.push(Math.floor(Math.sqrt(r2 - (i-0.5)*(i-0.5)) + 0.5));
                }
                const fast = r[0] ? { "idx": r[1], "val": r[2] } : { "idx": undefined, "val": 0 };
                if (slow) {
                    if (slow.idx !== fast.idx || slow.val !== fast.val || slowPattern !== JSON.stringify(obstruction.pattern))
                        throw new Error('AIMapBestTile mismatch: ' + JSON.stringify([fast, slow, radius]));
                    Engine.AIMapKernelVerified(0);
                }
                return fast;
            }
        }
        if (globalThis.__aiKernelVerify) Engine.AIMapKernelFallback();
        return originalBestTile.call(this, radius, obstruction);
    };
};
)AIJS";
}
