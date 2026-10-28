/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef INCLUDED_AITURNGATE
#define INCLUDED_AITURNGATE
#include <emscripten.h>
#include <functional>
#include <utility>
#include <vector>

// Optional browser candidate (WASM_AI_TURN_GATE). The turn manager starts a
// turn only once the threaded AI results that turn consumes are computed, so
// the frame loop keeps rendering instead of blocking at the result barrier.
// Only wall-clock timing changes: turns, commands and their order are the same.
// Predicates run on the sim thread; a false one only delays the turn.
namespace AITurnGate
{
#ifndef WASM_AI_TURN_GATE_MAX_HOLD_MS
#define WASM_AI_TURN_GATE_MAX_HOLD_MS 1e9
#endif
// A hold longer than this releases the turn, which then waits at the result
// barrier as without the gate: rendering during a long AI computation slows
// it and, through the turn manager's catch-up limit, the simulation rate.
inline constexpr double kMaxHoldMs = WASM_AI_TURN_GATE_MAX_HOLD_MS;

struct Entry { const void* owner; std::function<bool()> ready; };
inline std::vector<Entry> pending;
// True while a due turn waits for the gate. The frame loop then polls the gate
// and starts the next frame as soon as it opens, instead of at the next display
// signal, so that a held turn does not also wait for vsync.
inline bool held = false;
// The current hold's start, and whether it timed out; both reset by TurnStarted.
inline double heldSinceMs = -1;
inline bool released = false;

inline void TurnStarted()
{
	heldSinceMs = -1;
	released = false;
}

inline void Clear(const void* owner)
{
	std::erase_if(pending, [owner](const Entry& entry) { return entry.owner == owner; });
	held = false;
	TurnStarted();
}

inline void Set(const void* owner, std::function<bool()> ready)
{
	Clear(owner);
	pending.push_back({owner, std::move(ready)});
}

inline bool Ready()
{
	if (released)
		return true;
	for (const Entry& entry : pending)
		if (!entry.ready())
		{
			const double now = emscripten_get_now();
			if (heldSinceMs < 0)
				heldSinceMs = now;
			if (now - heldSinceMs < kMaxHoldMs)
				return false;
			released = true;
			return true;
		}
	return true;
}
}
#endif
