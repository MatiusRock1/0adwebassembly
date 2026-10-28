/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef INCLUDED_SIMTIMING
#define INCLUDED_SIMTIMING
// Diagnostic only (WASM_SIM_SCRIPT_TIMING): exclusive wall time of each message
// handler type and command type inside simulation turns, merged per turn into
// the table of slow turns (>= kSlowMs, excluding waits on other threads) or of
// the others. Timing every dispatch adds clock reads; never FPS evidence.
#include <algorithm>
#include <cstdint>
#include <emscripten.h>
#include <mutex>
#include <sstream>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

namespace SimTiming
{
#ifndef SIM_TIMING_SLOW_MS
#define SIM_TIMING_SLOW_MS 70
#endif
inline constexpr double kSlowMs = SIM_TIMING_SLOW_MS;

struct Stat { std::uint64_t calls = 0; double ms = 0, maxMs = 0; };
using Table = std::unordered_map<std::string, Stat>;

#ifndef SIM_TIMING_WORST_MS
#define SIM_TIMING_WORST_MS 250
#endif
inline constexpr double kWorstMs = SIM_TIMING_WORST_MS;

inline std::mutex mutex;
inline Table slowTable, otherTable;
inline std::uint64_t slowTurns = 0, otherTurns = 0;
inline double slowMs = 0, otherMs = 0, slowUnattributed = 0, otherUnattributed = 0;
// Turns of at least kWorstMs including waits: turn number, total and waited
// milliseconds, and their largest rows.
struct Worst { int turn; double totalMs, waitedMs; std::vector<std::pair<std::string, double>> rows; };
inline std::vector<Worst> worst;
inline int wrappedFunctions = 0;

inline thread_local Table current;
inline thread_local double excludedMs = 0;
inline thread_local bool inTurn = false;
struct Frame { double start, children; std::string key; };
inline thread_local std::vector<Frame> stack;

inline void Begin(std::string key)
{
	stack.push_back({emscripten_get_now(), 0, std::move(key)});
}

inline void End()
{
	if (stack.empty())
		return;
	Frame frame = std::move(stack.back());
	stack.pop_back();
	const double total = emscripten_get_now() - frame.start;
	const double exclusive = total - frame.children;
	Stat& stat = current[frame.key];
	++stat.calls;
	stat.ms += exclusive;
	if (exclusive > stat.maxMs)
		stat.maxMs = exclusive;
	if (!stack.empty())
		stack.back().children += total;
}

// Keys are built by the caller's lambda so that only scopes taken inside a
// turn format a string.
class Scope
{
public:
	template<typename KeyFn>
	explicit Scope(KeyFn&& key) : m_Active(inTurn)
	{
		if (m_Active)
			Begin(key());
	}
	~Scope()
	{
		if (m_Active)
			End();
	}
	Scope(const Scope&) = delete;
	Scope& operator=(const Scope&) = delete;
private:
	bool m_Active;
};

// Script entry points (registered as Engine.SimTimingBegin/End). Outside a
// turn they do nothing, so the scripted Begin/End pairs stay balanced.
inline thread_local unsigned scriptDepth = 0;
inline void ScriptBegin(const std::string& key)
{
	if (!inTurn)
		return;
	++scriptDepth;
	Begin(key);
}
inline void ScriptEnd()
{
	if (!inTurn || !scriptDepth)
		return;
	--scriptDepth;
	End();
}

// Diagnostic copy of Timer.prototype.OnUpdate that times each callback. Same
// order, deletion and repeat logic as the original; installed only when its
// source still matches the original's.
inline constexpr char TimerPatch[] = R"JS(
(function() {
    const iidNames = {};
    for (const key of Object.getOwnPropertyNames(globalThis))
        if (key.startsWith("IID_")) iidNames[globalThis[key]] = key.slice(4);
    // The Timer kernel (SimKernels.h) times its callbacks itself given the names.
    if (Timer.prototype.OnUpdate.toString().includes("__simTimingTimerName"))
    {
        globalThis.__simTimingTimerName = iid => iidNames[iid] || iid;
        return;
    }
    Timer.prototype.OnUpdate = function(msg)
    {
        this.turnLength = Math.round(msg.turnLength * 1000);
        this.time += this.turnLength;
        const run = [];
        this.timers.forEach((timer, id) =>
        {
            if (timer.time <= this.time)
                run.push(id);
        });
        for (const id of run)
        {
            const timer = this.timers.get(id);
            if (!timer)
                continue;
            const timerTargetComponent = Engine.QueryInterface(timer.entity, timer.iid);
            if (!timerTargetComponent)
            {
                this.timers.delete(id);
                continue;
            }
            Engine.SimTimingBegin("timer:" + (iidNames[timer.iid] || timer.iid) + "." + timer.functionName);
            try
            {
                timerTargetComponent[timer.functionName](timer.data, this.time - timer.time);
            }
            catch(e)
            {
                error(
                    "Error in timer on entity " + timer.entity + ", " +
                    "IID" + timer.iid + ", " +
                    "function " + timer.functionName + ": " +
                    e + "\n" +
                    e.stack.trimRight().replace(/^/mg, '  ') + "\n");
            }
            Engine.SimTimingEnd();
            if (!timer.repeatTime)
            {
                this.timers.delete(id);
                continue;
            }
            timer.time += timer.repeatTime;
            if (timer.time <= this.time)
                run.push(id);
        }
    };
})();
)JS";

// Diagnostic only: exclusive time rows "fn:<name>" for selected functions, so
// that handler rows split into the helpers they spend time in. Each wrapper
// passes this, the same arguments and the result or exception through.
inline constexpr char FunctionPatch[] = R"JS(
(function() {
    const targets = [
        ["ModifiersManager.prototype", ["ApplyModifiers", "ApplyTemplateModifiers", "FetchModifiedProperty", "Cache", "InvalidateCache"]],
        ["Attack.prototype", ["CanAttack", "PerformAttack", "GetPreference", "IsTargetInRange", "GetAttackEffectsData", "GetBestAttackAgainst", "StartAttacking", "CanEverReachTarget", "GetRange"]],
        ["Object.getPrototypeOf(AttackHelper)", ["HandleAttackEffects", "GetAttackBonus", "GetTotalAttackEffects", "CauseDamageOverArea"]],
        ["DelayedDamage.prototype", ["Hit"]],
        ["Health.prototype", ["TakeDamage", "Reduce", "HandleDeath", "CreateCorpse"]],
        ["Resistance.prototype", ["GetEffectiveResistanceAgainst", "GetResistanceOfForm"]],
        ["ResourceGatherer.prototype", ["RecalculateGatherRates", "RecalculateCapacities"]],
        ["UnitAI.prototype", ["Attack", "PushOrder", "ReplaceOrder", "MoveToTargetAttackRange", "CheckTargetRange", "CheckTargetVisible",
            "RespondToTargetedEntities", "FindNewTargets", "FindWalkAndFightTargets", "CanAttack", "AttackEntitiesByPreference"]],
        ["FSM.prototype", ["ProcessMessage", "SwitchToNextState"]],
        ["globalThis", ["GetFormationUnitAIs", "RemoveFromFormation", "ExtractFormations", "GetTechModifiedProperty", "MatchesClassList"]]
    ];
    let wrapped = 0;
    for (const [expression, names] of targets)
    {
        let object;
        try { object = (0, eval)(expression); } catch (e) { continue; }
        if (!object)
            continue;
        for (const name of names)
        {
            const original = object[name];
            if (typeof original !== "function")
                continue;
            const key = "fn:" + name;
            const wrapper = function(...args)
            {
                Engine.SimTimingBegin(key);
                try
                {
                    return original.apply(this, args);
                }
                finally
                {
                    Engine.SimTimingEnd();
                }
            };
            try { object[name] = wrapper; } catch (e) { continue; }
            if (object[name] === wrapper)
                ++wrapped;
        }
    }
    return wrapped;
})()
)JS";

class Turn
{
public:
	explicit Turn(int turn) : m_Start(emscripten_get_now()), m_TurnNumber(turn)
	{
		current.clear();
		stack.clear();
		excludedMs = 0;
		inTurn = true;
	}
	~Turn()
	{
		inTurn = false;
		const double total = emscripten_get_now() - m_Start;
		const double ms = total - excludedMs;
		// "ai:" rows are waits already excluded from the turn time.
		double attributed = 0;
		for (const auto& [key, stat] : current)
			if (key.rfind("ai:", 0) != 0)
				attributed += stat.ms;
		std::lock_guard lock(mutex);
		if (total >= kWorstMs && worst.size() < 64)
		{
			Worst entry{m_TurnNumber, total, excludedMs, {}};
			for (const auto& [key, stat] : current)
				entry.rows.emplace_back(key, stat.ms);
			std::sort(entry.rows.begin(), entry.rows.end(), [](const auto& a, const auto& b) { return a.second > b.second; });
			if (entry.rows.size() > 10)
				entry.rows.resize(10);
			worst.push_back(std::move(entry));
		}
		const bool slow = ms >= kSlowMs;
		Table& table = slow ? slowTable : otherTable;
		(slow ? slowTurns : otherTurns) += 1;
		(slow ? slowMs : otherMs) += ms;
		(slow ? slowUnattributed : otherUnattributed) += ms - attributed;
		for (const auto& [key, stat] : current)
		{
			Stat& merged = table[key];
			merged.calls += stat.calls;
			merged.ms += stat.ms;
			if (stat.maxMs > merged.maxMs)
				merged.maxMs = stat.maxMs;
		}
		current.clear();
	}
	Turn(const Turn&) = delete;
	Turn& operator=(const Turn&) = delete;
private:
	double m_Start;
	int m_TurnNumber;
};
}

extern "C" EMSCRIPTEN_KEEPALIVE inline const char* Phase45SimTiming()
{
	using namespace SimTiming;
	static std::string result;
	std::ostringstream out;
	const auto escape = [&out](const std::string& text) {
		for (const unsigned char c : text)
		{
			if (c == '"' || c == '\\') out << '\\';
			if (c < 32) out << '?'; else out << char(c);
		}
	};
	const auto table = [&](const char* name, const Table& rows) {
		out << ",\"" << name << "\":[";
		bool first = true;
		for (const auto& [key, stat] : rows)
		{
			if (!first) out << ',';
			first = false;
			out << "{\"key\":\"";
			escape(key);
			out << "\",\"calls\":" << stat.calls << ",\"ms\":" << stat.ms << ",\"maxMs\":" << stat.maxMs << '}';
		}
		out << ']';
	};
	std::lock_guard lock(mutex);
	out << "{\"diagnosticOnly\":true,\"slowThresholdMs\":" << kSlowMs << ",\"slowTurns\":" << slowTurns
		<< ",\"slowMs\":" << slowMs << ",\"slowUnattributedMs\":" << slowUnattributed << ",\"otherTurns\":" << otherTurns
		<< ",\"otherMs\":" << otherMs << ",\"otherUnattributedMs\":" << otherUnattributed;
	table("slow", slowTable);
	table("other", otherTable);
	out << ",\"wrappedFunctions\":" << wrappedFunctions << ",\"worstThresholdMs\":" << kWorstMs << ",\"worst\":[";
	for (std::size_t i = 0; i < worst.size(); ++i)
	{
		if (i) out << ',';
		out << "{\"turn\":" << worst[i].turn << ",\"totalMs\":" << worst[i].totalMs << ",\"waitedMs\":" << worst[i].waitedMs << ",\"rows\":[";
		for (std::size_t j = 0; j < worst[i].rows.size(); ++j)
		{
			if (j) out << ',';
			out << "{\"key\":\"";
			escape(worst[i].rows[j].first);
			out << "\",\"ms\":" << worst[i].rows[j].second << '}';
		}
		out << "]}";
	}
	out << "]}";
	result = out.str();
	return result.c_str();
}
#endif
