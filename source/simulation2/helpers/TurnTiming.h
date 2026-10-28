/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef INCLUDED_TURNTIMING
#define INCLUDED_TURNTIMING

// Optional browser candidate (WASM_PRESENT_PACING). The turn manager publishes
// the simulation time left before its next turn after every update, so that the
// browser frame clock can start the frame that will run the turn early. Read
// only by that clock: turns, commands and their order do not change.
namespace TurnTiming
{
// CTurnManager::m_DeltaSimTime after the last Update, in seconds: the next
// turn runs in the first update that brings it to zero or above.
inline float deltaSimTime = 0;
}
#endif
