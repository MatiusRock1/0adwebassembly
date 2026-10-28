/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef INCLUDED_AIDEFERREDSTART
#define INCLUDED_AIDEFERREDSTART
#include <algorithm>
#include <functional>
#include <utility>
#include <vector>

// Optional browser candidate (WASM_AI_DEFERRED_CAPTURE). The threaded AI client
// may postpone its JS state capture from the end of the turn until the turn
// frame has dispatched its Present. Tasks run on the sim thread, in order,
// before anything that can observe or mutate the captured state: the frame
// loop after rendering, the next turn, AI serialization and the result barrier.
// A task receives false when cancelled; it must then fail its pending result.
namespace AIDeferredStart
{
struct Task { const void* owner; std::function<void(bool)> run; };
inline std::vector<Task> pending;

inline void Schedule(const void* owner, std::function<void(bool)> run)
{
	pending.push_back({owner, std::move(run)});
}

// Runs every pending task, or only those of one owner.
inline void Run(const void* owner = nullptr)
{
	while (!pending.empty())
	{
		auto task = pending.begin();
		if (owner)
			while (task != pending.end() && task->owner != owner) ++task;
		if (task == pending.end()) return;
		auto run = std::move(task->run);
		pending.erase(task);
		run(true);
	}
}

inline bool IsPending(const void* owner)
{
	return std::any_of(pending.begin(), pending.end(), [owner](const Task& task) { return task.owner == owner; });
}

inline void Cancel(const void* owner)
{
	std::vector<Task> cancelled;
	std::erase_if(pending, [&](Task& task) {
		if (task.owner != owner) return false;
		cancelled.push_back(std::move(task));
		return true;
	});
	for (Task& task : cancelled) task.run(false);
}
}
#endif
