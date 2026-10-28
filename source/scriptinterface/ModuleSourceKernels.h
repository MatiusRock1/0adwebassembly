/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef INCLUDED_MODULESOURCEKERNELS
#define INCLUDED_MODULESOURCEKERNELS
// Optional browser candidate (WASM_AI_MODULE_KERNELS): exported module functions
// cannot be replaced from outside their module, so a guard is inserted into the
// source of an exact, known Petra module. The guard lets a native kernel compute a
// loop's result; when the kernel declines, the original loop runs. The guard goes
// on the loop's own line, so line numbers stay as they are.
#include <cstddef>
#include <cstdint>
#include <string>
#include <string_view>

namespace ModuleSourceKernels
{
// FNV-1a over the module's UTF-8 bytes.
inline std::uint32_t Hash(std::string_view text)
{
	std::uint32_t hash = 0x811c9dc5u;
	for (const unsigned char c : text)
		hash = (hash ^ c) * 0x01000193u;
	return hash;
}

// petra/mapModule.js createObstructionMap: the territory loop that fills
// obstructionTiles (AIMapKernels::ObstructionTiles, wrapper __aiObstructionTiles).
inline constexpr std::string_view kMapModule = "simulation/ai/petra/mapModule.js";
inline constexpr std::uint32_t kMapModuleHash = 0xeba24c7du;
inline constexpr std::string_view kObstructionLoop = "\tfor (let k = 0; k < territoryMap.data.length; ++k)\n";
inline constexpr std::string_view kObstructionGuard =
	"if (!(globalThis.__aiObstructionTiles && globalThis.__aiObstructionTiles(obstructionTiles, territoryMap, "
	"passabilityMap, passMap, obstructionMask, ratio, placementType != \"shore\", accessIndex, PlayerID, "
	"TERRITORY_PLAYER_MASK, TERRITORY_BLINKING_MASK, buildOwn, buildAlly, buildNeutral, buildEnemy, gameState))) ";

inline std::string Transform(std::string_view path, std::string code)
{
	if (path != kMapModule || Hash(code) != kMapModuleHash)
		return code;
	const std::size_t at = code.find(kObstructionLoop);
	if (at == std::string::npos || code.find(kObstructionLoop, at + 1) != std::string::npos)
		return code;
	// After the tab: "\tif (...) for (...)", the loop and its block as the if's body.
	code.insert(at + 1, kObstructionGuard);
	return code;
}
}
#endif
