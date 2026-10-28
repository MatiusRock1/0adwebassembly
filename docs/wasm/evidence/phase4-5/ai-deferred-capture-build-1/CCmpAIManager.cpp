/* Copyright (C) 2026 Wildfire Games.
 * This file is part of 0 A.D.
 *
 * 0 A.D. is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 2 of the License, or
 * (at your option) any later version.
 *
 * 0 A.D. is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with 0 A.D.  If not, see <http://www.gnu.org/licenses/>.
 */

#include "precompiled.h"

#include "ICmpAIManager.h"

#include "graphics/HeightMipmap.h"
#include "lib/alignment.h"
#include "lib/allocators/shared_ptr.h"
#include "lib/code_annotation.h"
#include "lib/debug.h"
#include "lib/file/vfs/vfs_path.h"
#include "lib/file/vfs/vfs_util.h"
#include "lib/os_path.h"
#include "lib/path.h"
#include "lib/tex/tex.h"
#include "lib/utf8.h"
#include "maths/FixedVector2D.h"
#include "ps/CLogger.h"
#include "ps/ConfigDB.h"
#include "ps/Filesystem.h"
#include "ps/Profile.h"
#include "ps/Profiler2.h"
#include "ps/TemplateLoader.h"
#include "ps/Util.h"
#include "ps/scripting/JSInterface_VFS.h"
#include "scriptinterface/FunctionWrapper.h"
#include "scriptinterface/JSON.h"
#include "scriptinterface/ModuleLoader.h"
#include "scriptinterface/Object.h"
#include "scriptinterface/Context.h"
#include "scriptinterface/Conversions.h"
#include "scriptinterface/Interface.h"
#include "scriptinterface/Request.h"
#include "scriptinterface/StructuredClone.h"
#include "simulation2/components/ICmpAIInterface.h"
#include "simulation2/components/ICmpCommandQueue.h"
#include "simulation2/components/ICmpPathfinder.h"
#include "simulation2/components/ICmpRangeManager.h"
#include "simulation2/components/ICmpTemplateManager.h"
#include "simulation2/components/ICmpTerritoryManager.h"
#include "simulation2/helpers/Grid.h"
#include "simulation2/helpers/HierarchicalPathfinder.h"
#include "simulation2/helpers/LongPathfinder.h"
#include "simulation2/helpers/PathGoal.h"
#include "simulation2/helpers/Pathfinding.h"
#include "simulation2/helpers/Player.h"
#include "simulation2/helpers/AIWorkerMailbox.h"
#include "simulation2/helpers/AIWorkerScript.h"
#if defined(WASM_AI_MAP_KERNELS)
#include "simulation2/helpers/AIMapKernels.h"
#endif
#if defined(WASM_AI_GUEST_PROFILE)
#include "simulation2/helpers/AIGuestProfiler.h"
#endif
#if defined(WASM_AI_DEFERRED_CAPTURE)
#include "simulation2/helpers/AIDeferredStart.h"
#include <iterator>
#endif
#include "simulation2/helpers/SimulationCommand.h"
#include "simulation2/serialization/DebugSerializer.h"
#include "simulation2/serialization/SerializeTemplates.h"
#include "simulation2/serialization/SerializedTypes.h"
#include "simulation2/serialization/StdDeserializer.h"
#include "simulation2/serialization/StdSerializer.h"
#include "simulation2/system/Component.h"

#include <boost/random/linear_congruential.hpp>
#include <cstring>
#include <js/Array.h>
#include <js/GCAPI.h>
#include <js/GCVector.h>
#include <js/PropertyAndElement.h>
#include <js/RootingAPI.h>
#include <js/TracingAPI.h>
#include <js/TypeDecls.h>
#include <js/Value.h>
#include <js/experimental/TypedData.h>
#include <map>
#include <memory>
#include <set>
#include <sstream>
#include <string>
#include <tuple>
#include <utility>
#include <vector>

extern void QuitEngine(int exitStatus);

/**
 * @file
 * Player AI interface.
 * AI is primarily scripted, and the CCmpAIManager component defined here
 * takes care of managing all the scripts.
 *
 * The original idea was to run CAIWorker in a separate thread to prevent
 * slow AIs from impacting framerate. However, copying the game-state every turn
 * proved difficult and rather slow itself (and isn't threadable, obviously).
 * For these reasons, the design was changed to a single-thread, same-compartment, different-realm design.
 * The AI can therefore directly use the simulation data via the 'Sim' & 'SimEngine' globals.
 * As a result, a lof of the code is still designed to be "thread-ready", but this no longer matters.
 *
 * TODO: despite the above, it would still be useful to allow the AI to run tasks asynchronously (and off-thread).
 * This could be implemented by having a separate JS runtime in a different thread,
 * that runs tasks and returns after a distinct # of simulation turns (to maintain determinism).
 *
 * Note also that the RL Interface, by default, uses the 'AI representation'.
 * This representation, alimented by the JS AIInterface/AIProxy tandem, is likely to grow smaller over time
 * as the AI uses more sim data directly.
 */

/**
 * AI computation orchestator for CCmpAIManager.
 */
class CAIWorker
{
private:
	class CAIPlayer
	{
		NONCOPYABLE(CAIPlayer);
	public:
		CAIPlayer(CAIWorker& worker, const std::wstring& aiName, player_id_t player,
			std::uint8_t difficulty, const std::wstring& behavior,
			std::shared_ptr<Script::Interface> scriptInterface) :
			m_Worker(worker), m_AIName(aiName), m_Player(player), m_Difficulty(difficulty), m_Behavior(behavior),
			m_ScriptInterface(scriptInterface), m_Obj(scriptInterface->GetGeneralJSContext())
		{
		}

		bool Initialise()
		{
			Script::Request rq(m_ScriptInterface);

			OsPath path = L"simulation/ai/" + m_AIName + L"/data.json";
			JS::RootedValue metadata(rq.cx);
			m_Worker.LoadMetadata(path, &metadata);
			if (metadata.isUndefined())
			{
				LOGERROR("Failed to create AI player: can't find {}", path.string8());
				return false;
			}

			// Get the constructor name from the metadata
			std::string filename;
			std::string constructor;
			JS::RootedValue ctor(rq.cx);
			if (!Script::HasProperty(rq, metadata, "filename"))
			{
				LOGERROR("Failed to create AI player: {}: missing 'filename'", path.string8());
				return false;
			}

			Script::GetProperty(rq, metadata, "filename", filename);


			auto result = m_ScriptInterface->GetModuleLoader().LoadModule(rq,
				"simulation/ai/" + utf8_from_wstring(m_AIName) + "/" + filename);

			g_ScriptContext->RunJobs();
			JS::RootedValue objectWithConstructor(rq.cx, JS::ObjectValue(*result.begin()->Get()));

			if (!Script::GetProperty(rq, metadata, "constructor", constructor))
			{
				LOGERROR("Failed to create AI player: {}: missing 'constructor'", path.string8());
				return false;
			}

			// Get the constructor function from the loaded scripts
			if (!Script::GetProperty(rq, objectWithConstructor, constructor.c_str(), &ctor)
			    || ctor.isNull())
			{
				LOGERROR("Failed to create AI player: {}: can't find constructor '{}'",
					path.string8(), constructor);
				return false;
			}

			Script::GetProperty(rq, metadata, "useShared", m_UseSharedComponent);

			// Set up the data to pass as the constructor argument
			JS::RootedValue settings(rq.cx);
			Script::CreateObject(
				rq,
				&settings,
				"player", m_Player,
				"difficulty", m_Difficulty,
				"behavior", m_Behavior);

			if (!m_UseSharedComponent)
			{
				ENSURE(m_Worker.m_HasLoadedEntityTemplates);
				Script::SetProperty(rq, settings, "templates", m_Worker.m_EntityTemplates, false);
			}

			JS::RootedValueVector argv(rq.cx);
			std::ignore = argv.append(settings.get());
			m_ScriptInterface->CallConstructor(ctor, argv, &m_Obj);

			if (m_Obj.get().isNull())
			{
				LOGERROR("Failed to create AI player: {}: error calling constructor '{}'",
					path.string8(), constructor);
				return false;
			}
			return true;
		}

		void Run(JS::HandleValue state, int playerID)
		{
			m_Commands.clear();
			Script::Request rq(m_ScriptInterface);
			Script::Function::CallVoid(rq, m_Obj, "HandleMessage", state, playerID);
		}
		// overloaded with a sharedAI part.
		// javascript can handle both natively on the same function.
		void Run(JS::HandleValue state, int playerID, JS::HandleValue SharedAI)
		{
			m_Commands.clear();
			Script::Request rq(m_ScriptInterface);
			Script::Function::CallVoid(rq, m_Obj, "HandleMessage", state, playerID, SharedAI);
		}
		void InitAI(JS::HandleValue SharedAI)
		{
			m_Commands.clear();
			Script::Request rq(m_ScriptInterface);
			Script::Function::CallVoid(rq, m_Obj, "Init", m_Player, SharedAI);
		}

		CAIWorker& m_Worker;
		std::wstring m_AIName;
		player_id_t m_Player;
		std::uint8_t m_Difficulty;
		std::wstring m_Behavior;
		bool m_UseSharedComponent;

		// Take care to keep this declaration before heap rooted members. Destructors of heap rooted
		// members have to be called before the context destructor.
		std::shared_ptr<Script::Interface> m_ScriptInterface;

		JS::PersistentRootedValue m_Obj;
		std::vector<Script::StructuredClone> m_Commands;
	};

public:
	struct SCommandSets
	{
		player_id_t player;
		std::vector<Script::StructuredClone> commands;
	};

	CAIWorker() :
		m_TurnNum(0),
		m_CommandsComputed(true),
		m_HasLoadedEntityTemplates(false),
		m_HasSharedComponent(false)
	{
	}

	~CAIWorker()
	{
		if (m_ScriptInterface)
			JS_RemoveExtraGCRootsTracer(m_ScriptInterface->GetGeneralJSContext(), Trace, this);
	}

	void Init(const Script::Interface& simInterface)
	{
		// Create the script interface in the same compartment as the simulation interface.
		// This will allow us to directly share data from the sim to the AI (and vice versa, should the need arise).
		Initialize(std::make_shared<Script::Interface>("Engine", "AI", simInterface,
			[](const VfsPath& path)
			{
				return path.string().find(L"simulation/ai/") == 0;
			}), &simInterface);
	}

	void InitIsolated(Script::Context& context)
	{
		Initialize(std::make_shared<Script::Interface>("Engine", "AI worker", context,
			[](const VfsPath& path) { return path.string().find(L"simulation/ai/") == 0; }), nullptr);
	}

	void Initialize(std::shared_ptr<Script::Interface> scriptInterface, const Script::Interface* simInterface)
	{
		m_ScriptInterface = std::move(scriptInterface);

		Script::Request rq(m_ScriptInterface);

		m_EntityTemplates.init(rq.cx);
		m_SharedAIObj.init(rq.cx);
		m_PassabilityMapVal.init(rq.cx);
		m_TerritoryMapVal.init(rq.cx);


		m_ScriptInterface->ReplaceNondeterministicRNG(m_RNG);

		m_ScriptInterface->SetCallbackData(static_cast<void*> (this));

		JS_AddExtraGCRootsTracer(m_ScriptInterface->GetGeneralJSContext(), Trace, this);

		if (simInterface)
		{
			Script::Request simrq(*simInterface);
			// Register the sim globals for easy & explicit access. Mark it replaceable for hotloading.
			JS::RootedValue global(rq.cx, simrq.globalValue());
			m_ScriptInterface->SetGlobal("Sim", global, true);
			JS::RootedValue scope(rq.cx, JS::ObjectValue(*simrq.nativeScope.get()));
			m_ScriptInterface->SetGlobal("SimEngine", scope, true);
		}
		else
			ENSURE(m_ScriptInterface->Eval(AIWorkerInstall));

#define REGISTER_FUNC_NAME(func, name) \
	Script::Function::Register<&CAIWorker::func, Script::Interface::ObjectFromCBData<CAIWorker>>(rq, name);

		REGISTER_FUNC_NAME(PostCommand, "PostCommand");
		Script::Function::Register<QuitEngine>(rq, "Exit");

		REGISTER_FUNC_NAME(ComputePathScript, "ComputePath");

		REGISTER_FUNC_NAME(DumpImage, "DumpImage");
		REGISTER_FUNC_NAME(GetTemplate, "GetTemplate");
#if defined(WASM_AI_MAP_KERNELS)
        REGISTER_FUNC_NAME(AIMapAddInfluence, "AIMapAddInfluence");
        REGISTER_FUNC_NAME(AIMapObstruction, "AIMapObstruction");
        ENSURE(m_ScriptInterface->Eval(AIMapKernels::Install));
#endif

#undef REGISTER_FUNC_NAME

		JSI_VFS::RegisterScriptFunctions_ReadOnlySimulation(rq);

		// Globalscripts may use VFS script functions
		m_ScriptInterface->LoadGlobalScripts();

	}

#if defined(WASM_AI_MAP_KERNELS)
    int AIMapObstruction(JS::HandleValue value, int width, int x, int y, int radius,
        JS::HandleValue patternValue)
    {
        if (!value.isObject() || width <= 0 || width > 32768 || radius < 0 || radius >= width ||
            x < radius || x >= width-radius || y < radius || y >= width-radius ||
            !patternValue.isObject()) return -2;
        Script::Request rq(m_ScriptInterface);
        JS::RootedObject patternObject(rq.cx,&patternValue.toObject());
        JS::RootedValue item(rq.cx);
        std::vector<double> pattern; pattern.reserve(radius+1);
        for (int dy=0; dy<=radius; ++dy)
        {
            if (!JS_GetElement(rq.cx,patternObject,dy,&item) || !item.isNumber()) return -2;
            const double v = item.toNumber();
            if (!std::isfinite(v) || v < 0 || v > radius || std::floor(v) != v) return -2;
            if (dy == 0 && v != radius) return -2;
            pattern.push_back(v);
        }
        JS::RootedObject object(rq.cx, &value.toObject());
        if (!JS_IsUint8Array(object) || JS_GetTypedArrayLength(object) != size_t(width)*width) return -2;
        bool shared=false;
        JS::AutoCheckCannotGC nogc;
        const auto* bytes=JS_GetUint8ArrayData(object,&shared,nogc);
        if (!bytes || shared) return -2;
        return AIMapKernels::Obstruction({bytes,size_t(width)*width},width,x,y,radius,pattern);
    }

    bool AIMapAddInfluence(JS::HandleValue value, int width, double cx, double cy,
        double distance, double strength, double maximum, int type)
    {
        if (!value.isObject() || width <= 0 || width > 32768 ||
            !std::isfinite(cx) || !std::isfinite(cy) || !std::isfinite(distance) ||
            !std::isfinite(strength) || !std::isfinite(maximum) || distance <= 0 ||
            distance < 1e-100 || distance > 32768 || std::abs(cx) > 32768 || std::abs(cy) > 32768 ||
            std::abs(strength) > 1e12 || maximum < 0 || maximum > 255 || type < 0 || type > 2)
            return false;
        Script::Request rq(m_ScriptInterface);
        JS::RootedObject object(rq.cx, &value.toObject());
        if (!JS_IsUint8Array(object)) return false;
        const size_t length = JS_GetTypedArrayLength(object);
        if (length % width || length / width > 32768) return false;
        const int height = length / width;
        const int x0 = std::floor(std::max(0., cx-distance));
        const int y0 = std::floor(std::max(0., cy-distance));
        const int x1 = std::floor(std::min(double(width-1), cx+distance));
        const int y1 = std::floor(std::min(double(height-1), cy+distance));
        bool shared = false;
        JS::AutoCheckCannotGC nogc;
        auto* bytes = JS_GetUint8ArrayData(object, &shared, nogc);
        if (!bytes || shared) return false;
        AIMapKernels::AddInfluence({bytes,length},width,x0,x1,y0,y1,cx,cy,distance,strength,maximum,type);
        return true;
    }
#endif
	bool HasLoadedEntityTemplates() const { return m_HasLoadedEntityTemplates; }

	void SetSnapshot(const Script::StructuredClone& snapshot)
	{
		Script::Request rq(m_ScriptInterface);
		JS::RootedValue value(rq.cx), global(rq.cx, rq.globalValue());
		Script::ReadStructuredClone(rq, snapshot, &value);
		if (!Script::Function::CallVoid(rq, global, "__installAIWorkerSnapshot", value))
			throw std::runtime_error("Failed to install AI snapshot");
	}

	void UpdateGameStateClone(const Script::StructuredClone& state)
	{
		Script::Request rq(m_ScriptInterface);
		JS::RootedValue value(rq.cx);
		Script::ReadStructuredClone(rq, state, &value);
		UpdateGameState(value);
	}

	void LoadEntityTemplatesClone(const Script::StructuredClone& templates)
	{
		Script::Request rq(m_ScriptInterface);
		Script::ReadStructuredClone(rq, templates, &m_EntityTemplates);
		m_HasLoadedEntityTemplates = true;
	}

	void AllowInitializationEffects(bool allow)
	{
		ENSURE(m_ScriptInterface->Eval(allow ? "__aiAllowEffects = true" : "__aiAllowEffects = false"));
	}

	Script::StructuredClone TakeInitializationEffects()
	{
		Script::Request rq(m_ScriptInterface);
		JS::RootedValue value(rq.cx);
		ENSURE(m_ScriptInterface->Eval("__aiEffects.splice(0)", &value));
		return Script::WriteStructuredClone(rq, value);
	}

	void PostCommand(int playerid, JS::HandleValue cmd)
	{
		Script::Request rq(m_ScriptInterface);
		for (size_t i=0; i<m_Players.size(); i++)
		{
			if (m_Players[i]->m_Player == playerid)
			{
				m_Players[i]->m_Commands.push_back(Script::WriteStructuredClone(rq, cmd));
				return;
			}
		}

		LOGERROR("Invalid playerid in PostCommand!");
	}

	JS::Value ComputePathScript(JS::HandleValue position, JS::HandleValue goal, pass_class_t passClass)
	{
		Script::Request rq(m_ScriptInterface);

		CFixedVector2D pos, goalPos;
		std::vector<CFixedVector2D> waypoints;
		JS::RootedValue retVal(rq.cx);

		Script::FromJSVal(rq, position, pos);
		Script::FromJSVal(rq, goal, goalPos);

		ComputePath(pos, goalPos, passClass, waypoints);
		Script::ToJSVal(rq, &retVal, waypoints);

		return retVal;
	}

	void ComputePath(const CFixedVector2D& pos, const CFixedVector2D& goal, pass_class_t passClass, std::vector<CFixedVector2D>& waypoints)
	{
		WaypointPath ret;
		PathGoal pathGoal = { PathGoal::POINT, goal.X, goal.Y };
		m_LongPathfinder.ComputePath(m_HierarchicalPathfinder, pos.X, pos.Y, pathGoal, passClass, ret);

		for (Waypoint& wp : ret.m_Waypoints)
			waypoints.emplace_back(wp.x, wp.z);
	}

	CParamNode GetTemplate(const std::string& name)
	{
		if (!m_TemplateLoader.TemplateExists(name))
			return CParamNode(false);
		return m_TemplateLoader.GetTemplateFileData(name).GetOnlyChild();
	}

	/**
	 * Debug function for AI scripts to dump 2D array data (e.g. terrain tile weights).
	 */
	void DumpImage(const std::wstring& name, const std::vector<std::uint32_t>& data, std::uint32_t w,
		std::uint32_t h, std::uint32_t max)
	{
		// TODO: this is totally not threadsafe.
		VfsPath filename = L"screenshots/aidump/" + name;

		if (data.size() != w*h)
		{
			debug_warn(L"DumpImage: data size doesn't match w*h");
			return;
		}

		if (max == 0)
		{
			debug_warn(L"DumpImage: max must not be 0");
			return;
		}

		const size_t bpp = 8;
		int flags = TEX_BOTTOM_UP|TEX_GREY;

		const size_t img_size = w * h * bpp/8;
		const size_t hdr_size = tex_hdr_size(filename);
		std::shared_ptr<std::uint8_t> buf;
		AllocateAligned(buf, hdr_size+img_size, maxSectorSize);
		Tex t;
		if (t.wrap(w, h, bpp, flags, buf, hdr_size) < 0)
			return;

		std::uint8_t* img = buf.get() + hdr_size;
		for (size_t i = 0; i < data.size(); ++i)
			img[i] = static_cast<std::uint8_t>((data[i] * 255) / max);

		tex_write(&t, filename);
	}

	void SetRNGSeed(std::uint32_t seed)
	{
		m_RNG.seed(seed);
	}

	bool TryLoadSharedComponent()
	{
		Script::Request rq(m_ScriptInterface);

		// we don't need to load it.
		if (!std::exchange(m_HasSharedComponent, true))
			return false;

		auto result = m_ScriptInterface->GetModuleLoader().LoadModule(rq,
			"simulation/ai/common-api/shared.js");

		g_ScriptContext->RunJobs();

		// mainly here for the error messages
#if defined(WASM_AI_MAP_KERNELS)
        auto maps = m_ScriptInterface->GetModuleLoader().LoadModule(rq,
            "simulation/ai/common-api/map-module.js");
        g_ScriptContext->RunJobs();
        JS::RootedValue mapModule(rq.cx, JS::ObjectValue(*maps.begin()->Get()));
        JS::RootedValue global(rq.cx, rq.globalValue());
        ENSURE(Script::Function::CallVoid(rq, global, "__installAIMapKernels", mapModule));
#endif
		OsPath path = L"simulation/ai/common-api/";

		// Constructor name is SharedScript, it's in the module API3
		// TODO: Hardcoding this is bad, we need a smarter way.
		JS::RootedValue AIModule(rq.cx, JS::ObjectValue(*result.begin()->Get()));
		JS::RootedValue ctor(rq.cx);

		if (!Script::GetProperty(rq, AIModule, "SharedScript", &ctor)
		    || ctor.isUndefined())
		{
			LOGERROR("Failed to create shared AI component: {}: can't find constructor '{}'",
				path.string8(), "SharedScript");
			return false;
		}

		// Set up the data to pass as the constructor argument
		JS::RootedValue playersID(rq.cx);
		Script::CreateObject(rq, &playersID);

		for (size_t i = 0; i < m_Players.size(); ++i)
		{
			JS::RootedValue val(rq.cx);
			Script::ToJSVal(rq, &val, m_Players[i]->m_Player);
			Script::SetPropertyInt(rq, playersID, i, val, true);
		}

		ENSURE(m_HasLoadedEntityTemplates);

		JS::RootedValue settings(rq.cx);
		Script::CreateObject(
			rq,
			&settings,
			"players", playersID,
			"templates", m_EntityTemplates);

		JS::RootedValueVector argv(rq.cx);
		std::ignore = argv.append(settings);
		m_ScriptInterface->CallConstructor(ctor, argv, &m_SharedAIObj);

		if (m_SharedAIObj.get().isNull())
		{
			LOGERROR("Failed to create shared AI component: {}: error calling constructor '{}'",
				path.string8(), "SharedScript");
			return false;
		}

		return true;
	}

	bool AddPlayer(const std::wstring& aiName, player_id_t player, std::uint8_t difficulty,
		const std::wstring& behavior)
	{
		std::shared_ptr<CAIPlayer> ai = std::make_shared<CAIPlayer>(*this, aiName, player, difficulty, behavior, m_ScriptInterface);
		if (!ai->Initialise())
			return false;

		// this will be set to true if we need to load the shared Component.
		if (!m_HasSharedComponent)
			m_HasSharedComponent = ai->m_UseSharedComponent;

		m_Players.push_back(ai);

		return true;
	}

	bool RunGamestateInit(const Script::StructuredClone& gameState,
		const Grid<NavcellData>& passabilityMap, const Grid<std::uint8_t>& territoryMap,
		const std::map<std::string, pass_class_t>& nonPathfindingPassClassMasks,
		const std::map<std::string, pass_class_t>& pathfindingPassClassMasks)
	{
		// this will be run last by InitGame.js, passing the full game representation.
		// For now it will run for the shared Component.
		// This is NOT run during deserialization.
		Script::Request rq(m_ScriptInterface);

		JS::RootedValue state(rq.cx);
		Script::ReadStructuredClone(rq, gameState, &state);
		Script::ToJSVal(rq, &m_PassabilityMapVal, passabilityMap);
		Script::ToJSVal(rq, &m_TerritoryMapVal, territoryMap);

		m_PassabilityMap = passabilityMap;
		m_NonPathfindingPassClasses = nonPathfindingPassClassMasks;
		m_PathfindingPassClasses = pathfindingPassClassMasks;

		m_LongPathfinder.Reload(&m_PassabilityMap);
		m_HierarchicalPathfinder.Recompute(&m_PassabilityMap, nonPathfindingPassClassMasks, pathfindingPassClassMasks);

		if (m_HasSharedComponent)
		{
			Script::SetProperty(rq, state, "passabilityMap", m_PassabilityMapVal, true);
			Script::SetProperty(rq, state, "territoryMap", m_TerritoryMapVal, true);
			Script::Function::CallVoid(rq, m_SharedAIObj, "init", state);

			for (size_t i = 0; i < m_Players.size(); ++i)
			{
				if (m_HasSharedComponent && m_Players[i]->m_UseSharedComponent)
					m_Players[i]->InitAI(m_SharedAIObj);
			}
		}

		return true;
	}

	void UpdateGameState(JS::HandleValue gameState)
	{
		ENSURE(m_CommandsComputed);
		m_GameState.reset();
		m_GameState.init(Script::Request(m_ScriptInterface).cx, gameState);
	}

	void UpdatePathfinder(const Grid<NavcellData>& passabilityMap, bool globallyDirty,
		const Grid<std::uint8_t>& dirtinessGrid, bool justDeserialized,
		const std::map<std::string, pass_class_t>& nonPathfindingPassClassMasks,
		const std::map<std::string, pass_class_t>& pathfindingPassClassMasks)
	{
		ENSURE(m_CommandsComputed);
		bool dimensionChange = m_PassabilityMap.m_W != passabilityMap.m_W || m_PassabilityMap.m_H != passabilityMap.m_H;

		m_PassabilityMap = passabilityMap;
		if (globallyDirty)
		{
			m_LongPathfinder.Reload(&m_PassabilityMap);
			m_HierarchicalPathfinder.Recompute(&m_PassabilityMap, nonPathfindingPassClassMasks, pathfindingPassClassMasks);
		}
		else
		{
			m_LongPathfinder.Update(&m_PassabilityMap);
			m_HierarchicalPathfinder.Update(&m_PassabilityMap, dirtinessGrid);
		}

		Script::Request rq(m_ScriptInterface);
		if (dimensionChange || justDeserialized)
			Script::ToJSVal(rq, &m_PassabilityMapVal, m_PassabilityMap);
		else
		{
			// Avoid a useless memory reallocation followed by a garbage collection.
			JS::RootedObject mapObj(rq.cx, &m_PassabilityMapVal.toObject());
			JS::RootedValue mapData(rq.cx);
			ENSURE(JS_GetProperty(rq.cx, mapObj, "data", &mapData));
			JS::RootedObject dataObj(rq.cx, &mapData.toObject());

			std::uint32_t length = 0;
			ENSURE(JS::GetArrayLength(rq.cx, dataObj, &length));
			std::uint32_t nbytes = static_cast<std::uint32_t>(length * sizeof(NavcellData));

			bool sharedMemory;
			JS::AutoCheckCannotGC nogc;
			memcpy((void*)JS_GetUint16ArrayData(dataObj, &sharedMemory, nogc), m_PassabilityMap.m_Data, nbytes);
		}
	}

	void UpdateTerritoryMap(const Grid<std::uint8_t>& territoryMap)
	{
		ENSURE(m_CommandsComputed);
		bool dimensionChange = m_TerritoryMap.m_W != territoryMap.m_W || m_TerritoryMap.m_H != territoryMap.m_H;

		m_TerritoryMap = territoryMap;

		Script::Request rq(m_ScriptInterface);
		if (dimensionChange)
			Script::ToJSVal(rq, &m_TerritoryMapVal, m_TerritoryMap);
		else
		{
			// Avoid a useless memory reallocation followed by a garbage collection.
			JS::RootedObject mapObj(rq.cx, &m_TerritoryMapVal.toObject());
			JS::RootedValue mapData(rq.cx);
			ENSURE(JS_GetProperty(rq.cx, mapObj, "data", &mapData));
			JS::RootedObject dataObj(rq.cx, &mapData.toObject());

			std::uint32_t length = 0;
			ENSURE(JS::GetArrayLength(rq.cx, dataObj, &length));
			std::uint32_t nbytes = static_cast<std::uint32_t>(length * sizeof(std::uint8_t));

			bool sharedMemory;
			JS::AutoCheckCannotGC nogc;
			memcpy((void*)JS_GetUint8ArrayData(dataObj, &sharedMemory, nogc), m_TerritoryMap.m_Data, nbytes);
		}
	}

	void StartComputation()
	{
		m_CommandsComputed = false;
	}

	void WaitToFinishComputation()
	{
		if (!m_CommandsComputed)
		{
			PerformComputation();
			m_CommandsComputed = true;
		}
	}

	void GetCommands(std::vector<SCommandSets>& commands)
	{
		WaitToFinishComputation();

		commands.clear();
		commands.resize(m_Players.size());
		for (size_t i = 0; i < m_Players.size(); ++i)
		{
			commands[i].player = m_Players[i]->m_Player;
			commands[i].commands = m_Players[i]->m_Commands;
		}
	}

	void LoadEntityTemplates(const std::vector<std::pair<std::string, const CParamNode*> >& templates)
	{
		Script::Request rq(m_ScriptInterface);

		m_HasLoadedEntityTemplates = true;

		Script::CreateObject(rq, &m_EntityTemplates);

		JS::RootedValue val(rq.cx);
		for (size_t i = 0; i < templates.size(); ++i)
		{
			templates[i].second->ToJSVal(rq, false, &val);
			Script::SetProperty(rq, m_EntityTemplates, templates[i].first.c_str(), val, true);
		}
	}

	void Serialize(std::ostream& stream, bool isDebug)
	{
		WaitToFinishComputation();

		if (isDebug)
		{
			CDebugSerializer serializer(*m_ScriptInterface, stream);
			serializer.Indent(4);
			SerializeState(serializer);
		}
		else
		{
			CStdSerializer serializer(*m_ScriptInterface, stream);
			SerializeState(serializer);
		}
	}

	void SerializeState(ISerializer& serializer)
	{
		if (m_Players.empty())
			return;

		Script::Request rq(m_ScriptInterface);

		std::stringstream rngStream;
		rngStream << m_RNG;
		serializer.StringASCII("rng", rngStream.str(), 0, 32);

		serializer.NumberU32_Unbounded("turn", m_TurnNum);

		serializer.Bool("useSharedScript", m_HasSharedComponent);
		if (m_HasSharedComponent)
			serializer.ScriptVal("sharedData", &m_SharedAIObj);
		for (size_t i = 0; i < m_Players.size(); ++i)
		{
			serializer.String("name", m_Players[i]->m_AIName, 1, 256);
			serializer.NumberI32_Unbounded("player", m_Players[i]->m_Player);
			serializer.NumberU8_Unbounded("difficulty", m_Players[i]->m_Difficulty);
			serializer.String("behavior", m_Players[i]->m_Behavior, 1, 256);

			serializer.NumberU32_Unbounded("num commands", static_cast<std::uint32_t>(m_Players[i]->m_Commands.size()));
			for (size_t j = 0; j < m_Players[i]->m_Commands.size(); ++j)
			{
				JS::RootedValue val(rq.cx);
				Script::ReadStructuredClone(rq, m_Players[i]->m_Commands[j], &val);
				serializer.ScriptVal("command", &val);
			}

			serializer.ScriptVal("data", &m_Players[i]->m_Obj);
		}

		// AI pathfinder
		Serializer(serializer, "non pathfinding pass classes", m_NonPathfindingPassClasses);
		Serializer(serializer, "pathfinding pass classes", m_PathfindingPassClasses);
		serializer.NumberU16_Unbounded("pathfinder grid w", m_PassabilityMap.m_W);
		serializer.NumberU16_Unbounded("pathfinder grid h", m_PassabilityMap.m_H);
		serializer.RawBytes("pathfinder grid data",
			reinterpret_cast<const std::uint8_t*>(m_PassabilityMap.m_Data),
			m_PassabilityMap.m_W*m_PassabilityMap.m_H*sizeof(NavcellData));
	}

	void Deserialize(std::istream& stream, std::uint32_t numAis)
	{
		m_PlayerMetadata.clear();
		m_Players.clear();

		if (numAis == 0)
			return;

		Script::Request rq(m_ScriptInterface);

		ENSURE(m_CommandsComputed); // deserializing while we're still actively computing would be bad

		CStdDeserializer deserializer(*m_ScriptInterface, stream);

		std::string rngString;
		std::stringstream rngStream;
		deserializer.StringASCII("rng", rngString, 0, 32);
		rngStream << rngString;
		rngStream >> m_RNG;

		deserializer.NumberU32_Unbounded("turn", m_TurnNum);

		deserializer.Bool("useSharedScript", m_HasSharedComponent);
		if (m_HasSharedComponent)
		{
			TryLoadSharedComponent();
			deserializer.ScriptObjectAssign("sharedData", m_SharedAIObj);
		}

		for (size_t i = 0; i < numAis; ++i)
		{
			std::wstring name;
			player_id_t player;
			std::uint8_t difficulty;
			std::wstring behavior;
			deserializer.String("name", name, 1, 256);
			deserializer.NumberI32_Unbounded("player", player);
			deserializer.NumberU8_Unbounded("difficulty",difficulty);
			deserializer.String("behavior", behavior, 1, 256);
			if (!AddPlayer(name, player, difficulty, behavior))
				throw PSERROR_Deserialize_ScriptError();

			std::uint32_t numCommands;
			deserializer.NumberU32_Unbounded("num commands", numCommands);
			m_Players.back()->m_Commands.reserve(numCommands);
			for (size_t j = 0; j < numCommands; ++j)
			{
				JS::RootedValue val(rq.cx);
				deserializer.ScriptVal("command", &val);
				m_Players.back()->m_Commands.push_back(Script::WriteStructuredClone(rq, val));
			}

			deserializer.ScriptObjectAssign("data", m_Players.back()->m_Obj);
		}

		// AI pathfinder
		Serializer(deserializer, "non pathfinding pass classes", m_NonPathfindingPassClasses);
		Serializer(deserializer, "pathfinding pass classes", m_PathfindingPassClasses);
		std::uint16_t mapW, mapH;
		deserializer.NumberU16_Unbounded("pathfinder grid w", mapW);
		deserializer.NumberU16_Unbounded("pathfinder grid h", mapH);
		m_PassabilityMap = Grid<NavcellData>(mapW, mapH);
		deserializer.RawBytes("pathfinder grid data",
			reinterpret_cast<std::uint8_t*>(m_PassabilityMap.m_Data), mapW * mapH * sizeof(NavcellData));
		m_LongPathfinder.Reload(&m_PassabilityMap);
		m_HierarchicalPathfinder.Recompute(&m_PassabilityMap, m_NonPathfindingPassClasses, m_PathfindingPassClasses);
	}

	int getPlayerSize()
	{
		return m_Players.size();
	}

private:
	static void Trace(JSTracer *trc, void *data)
	{
		reinterpret_cast<CAIWorker*>(data)->TraceMember(trc);
	}

	void TraceMember(JSTracer *trc)
	{
		for (std::pair<const VfsPath, JS::Heap<JS::Value>>& metadata : m_PlayerMetadata)
			JS::TraceEdge(trc, &metadata.second, "CAIWorker::m_PlayerMetadata");
	}

	void LoadMetadata(const VfsPath& path, JS::MutableHandleValue out)
	{
		if (m_PlayerMetadata.find(path) == m_PlayerMetadata.end())
		{
			// Load and cache the AI player metadata
			Script::ReadJSONFile(Script::Request(m_ScriptInterface), path, out);
			m_PlayerMetadata[path] = JS::Heap<JS::Value>(out);
			return;
		}
		out.set(m_PlayerMetadata[path].get());
	}

	void PerformComputation()
	{
		// Deserialize the game state, to pass to the AI's HandleMessage
		Script::Request rq(m_ScriptInterface);
		{
			PROFILE3("AI compute read state");
			Script::SetProperty(rq, m_GameState, "passabilityMap", m_PassabilityMapVal, true);
			Script::SetProperty(rq, m_GameState, "territoryMap", m_TerritoryMapVal, true);
		}

		// It would be nice to do
		//   Script::FreezeObject(rq, state.get(), true);
		// to prevent AI scripts accidentally modifying the state and
		// affecting other AI scripts they share it with. But the performance
		// cost is far too high, so we won't do that.
		// If there is a shared component, run it

		if (m_HasSharedComponent)
		{
			PROFILE3("AI run shared component");
			Script::Function::CallVoid(rq, m_SharedAIObj, "onUpdate", m_GameState);
		}

		for (size_t i = 0; i < m_Players.size(); ++i)
		{
			PROFILE3("AI script");
			PROFILE2_ATTR("player: %d", m_Players[i]->m_Player);
			PROFILE2_ATTR("script: %ls", m_Players[i]->m_AIName.c_str());

			if (m_HasSharedComponent && m_Players[i]->m_UseSharedComponent)
				m_Players[i]->Run(m_GameState, m_Players[i]->m_Player, m_SharedAIObj);
			else
				m_Players[i]->Run(m_GameState, m_Players[i]->m_Player);
		}
	}

	std::shared_ptr<Script::Interface> m_ScriptInterface;
	boost::rand48 m_RNG;
	std::uint32_t m_TurnNum;

	JS::PersistentRootedValue m_EntityTemplates;
	bool m_HasLoadedEntityTemplates;

	std::map<VfsPath, JS::Heap<JS::Value>> m_PlayerMetadata;
	std::vector<std::shared_ptr<CAIPlayer>> m_Players; // use shared_ptr just to avoid copying

	bool m_HasSharedComponent;
	JS::PersistentRootedValue m_SharedAIObj;
	std::vector<SCommandSets> m_Commands;

	std::set<std::wstring> m_LoadedModules;

	JS::PersistentRootedValue m_GameState;
	Grid<NavcellData> m_PassabilityMap;
	JS::PersistentRootedValue m_PassabilityMapVal;
	Grid<std::uint8_t> m_TerritoryMap;
	JS::PersistentRootedValue m_TerritoryMapVal;

	std::map<std::string, pass_class_t> m_NonPathfindingPassClasses;
	std::map<std::string, pass_class_t> m_PathfindingPassClasses;
	HierarchicalPathfinder m_HierarchicalPathfinder;
	LongPathfinder m_LongPathfinder;

	bool m_CommandsComputed;

	CTemplateLoader m_TemplateLoader;
};


// The client alone touches simulation objects. All actor payloads are owned
// clones/copies, except the exclusively handed-off deserialize stream while
// the caller synchronously waits. No realm, rooting handle or component moves.
class CAIWorkerClient
{
    using Commands = std::vector<CAIWorker::SCommandSets>;
    struct Result { uint64_t generation, sequence; Commands commands; };
    std::unique_ptr<CAIWorker> m_Local;
    std::unique_ptr<AIWorkerMailbox<CAIWorker>> m_Mailbox;
    const Script::Interface* m_Simulation = nullptr;
    std::shared_future<Result> m_Result;
    uint64_t m_Generation = 0, m_Sequence = 0;
    bool m_Isolated = false;
    int m_PlayerCount = 0;
    std::vector<std::function<void(CAIWorker&)>> m_TurnUpdates;

    template<class F> auto Call(F function)
    {
#if defined(WASM_AI_DEFERRED_CAPTURE)
        // Keep control messages FIFO behind a postponed computation.
        AIDeferredStart::Run(this);
#endif
        if (m_Mailbox) return m_Mailbox->Submit(std::move(function)).get();
        return function(*m_Local);
    }
    template<class F> void PrepareTurn(F function)
    {
        // All inputs are owned clones/copies, captured at the original boundary.
        // Submit them with computation once, without a handshake per field.
        if (m_Mailbox) m_TurnUpdates.emplace_back(std::move(function));
        else function(*m_Local);
    }
    Script::StructuredClone Capture()
    {
        PROFILE2("AI worker capture");
        Script::Request rq(*m_Simulation);
        JS::RootedValue value(rq.cx), global(rq.cx, rq.globalValue());
        if (!Script::Function::Call(rq, global, "__captureAIWorkerSnapshot", &value))
            throw std::runtime_error("Failed to capture AI simulation snapshot");
        auto clone = Script::WriteStructuredClone(rq, value);
        if (!clone) throw std::runtime_error("Failed to clone AI snapshot");
        return clone;
    }
    static auto Computation(uint64_t generation, uint64_t sequence, std::vector<std::function<void(CAIWorker&)>> updates)
    {
        return [generation, sequence, updates = std::move(updates)](CAIWorker& w) {
#if defined(WASM_AI_GUEST_PROFILE)
            AIGuestSampling::Profiler::Computing sampling;
#endif
            for (const auto& update : updates) update(w);
            w.StartComputation();
            Result result{generation, sequence, {}};
            w.GetCommands(result.commands);
            g_ScriptContext->MaybeIncrementalGC();
            return result;
        };
    }
public:
#if defined(WASM_AI_DEFERRED_CAPTURE)
    ~CAIWorkerClient() { AIDeferredStart::Cancel(this); }
#endif
    void Init(const Script::Interface& simulation)
    {
#if defined(WASM_AI_DEFERRED_CAPTURE)
        AIDeferredStart::Cancel(this);
#endif
        m_Mailbox.reset(); m_Local.reset(); m_Result = {};
        m_TurnUpdates.clear(); m_PlayerCount = 0;
        ++m_Generation; m_Sequence = 0; m_Simulation = &simulation;
        std::string mode = "sync";
#if defined(WASM_AI_WORKER)
        mode = CConfigDB::GetIfInitialised("aiworker.mode", std::string("threaded"));
#endif
        if (mode != "sync" && mode != "isolated-sync" && mode != "threaded")
            throw std::runtime_error("Unknown aiworker.mode");
        m_Isolated = mode != "sync";
        // Preserve the helper's bytecode/ICs across turns. Only its function
        // is reused: every call still captures fresh state at the same boundary.
#if defined(WASM_AI_DENSE_SNAPSHOT)
        if (m_Isolated && !simulation.Eval(AIWorkerCaptureDense))
#else
        if (m_Isolated && !simulation.Eval(AIWorkerCapture))
#endif
            throw std::runtime_error("Failed to install AI snapshot capture");
        if (mode == "threaded")
        {
            m_Mailbox = std::make_unique<AIWorkerMailbox<CAIWorker>>([] {
                g_Profiler2.RegisterCurrentThread("AI worker");
                // Same heap policy as the original main scripting context.
                g_ScriptContext = std::make_shared<Script::Context>(384 * 1024 * 1024, 12 * 1024 * 1024);
                auto worker = std::make_unique<CAIWorker>();
                worker->InitIsolated(*g_ScriptContext);
#if defined(WASM_AI_GUEST_PROFILE)
                AIGuestSampling::owner = std::make_unique<AIGuestSampling::Profiler>(g_ScriptContext->GetGeneralJSContext());
#endif
                return worker;
            }, [] {
#if defined(WASM_AI_GUEST_PROFILE)
                AIGuestSampling::owner.reset();
#endif
                g_ScriptContext.reset(); });
        }
        else
        {
            m_Local = std::make_unique<CAIWorker>();
            if (m_Isolated) m_Local->InitIsolated(simulation.GetContext());
            else m_Local->Init(simulation);
        }
        LOGMESSAGE("AI worker mode: {}", mode);
    }
    bool HasLoadedEntityTemplates() { return Call([](CAIWorker& w) { return w.HasLoadedEntityTemplates(); }); }
    int getPlayerSize() { return m_Mailbox ? m_PlayerCount : m_Local->getPlayerSize(); }
    void SetRNGSeed(uint32_t seed) { Call([seed](CAIWorker& w) { w.SetRNGSeed(seed); }); }
    void TryLoadSharedComponent() { Call([](CAIWorker& w) { w.TryLoadSharedComponent(); }); }
    void AddPlayer(const std::wstring& name, player_id_t player, uint8_t difficulty, const std::wstring& behavior)
    { m_PlayerCount = Call([=](CAIWorker& w) { w.AddPlayer(name, player, difficulty, behavior); return w.getPlayerSize(); }); }
    void LoadEntityTemplates(const std::vector<std::pair<std::string, const CParamNode*>>& templates)
    {
        if (!m_Isolated) { m_Local->LoadEntityTemplates(templates); return; }
        Script::Request rq(*m_Simulation);
        JS::RootedValue object(rq.cx), value(rq.cx);
        Script::CreateObject(rq, &object);
        for (const auto& [name, node] : templates)
        {
            node->ToJSVal(rq, false, &value);
            Script::SetProperty(rq, object, name.c_str(), value, true);
        }
        auto clone = Script::WriteStructuredClone(rq, object);
        if (!clone) throw std::runtime_error("Failed to clone AI templates");
        Call([clone](CAIWorker& w) { w.LoadEntityTemplatesClone(clone); });
    }
    void RunGamestateInit(const Script::StructuredClone& state,
        const Grid<NavcellData>& passability, const Grid<uint8_t>& territory,
        const std::map<std::string, pass_class_t>& nonPath, const std::map<std::string, pass_class_t>& path)
    {
        if (!m_Isolated) { m_Local->RunGamestateInit(state, passability, territory, nonPath, path); return; }
        auto snapshot = Capture();
        auto effects = Call([=](CAIWorker& w) {
            w.SetSnapshot(snapshot); w.AllowInitializationEffects(true);
            w.RunGamestateInit(state, passability, territory, nonPath, path);
            w.AllowInitializationEffects(false);
            return w.TakeInitializationEffects();
        });
        Script::Request rq(*m_Simulation);
        JS::RootedValue value(rq.cx);
        Script::ReadStructuredClone(rq, effects, &value);
        JS::RootedValue global(rq.cx, rq.globalValue());
        // The apply script clears this temporary slot after consuming it.
        // SetProperty's constant=true makes it permanently read-only.
        ENSURE(Script::SetProperty(rq, global, "__aiWorkerEffects", value, false));
        if (!m_Simulation->Eval(AIWorkerApplyEffects))
            throw std::runtime_error("Failed to apply AI initialization effects");
    }
    void UpdateGameState(JS::HandleValue state)
    {
        if (!m_Isolated) { m_Local->UpdateGameState(state); return; }
        auto snapshot = Capture();
        auto clone = Script::WriteStructuredClone(Script::Request(*m_Simulation), state);
        if (!clone) throw std::runtime_error("Failed to clone AI state");
        PrepareTurn([snapshot, clone](CAIWorker& w) { w.SetSnapshot(snapshot); w.UpdateGameStateClone(clone); });
    }
    void UpdatePathfinder(const Grid<NavcellData>& map, bool global,
        const Grid<uint8_t>& dirty, bool deserialized,
        const std::map<std::string, pass_class_t>& nonPath, const std::map<std::string, pass_class_t>& path)
    { PrepareTurn([=](CAIWorker& w) { w.UpdatePathfinder(map, global, dirty, deserialized, nonPath, path); }); }
    void UpdateTerritoryMap(const Grid<uint8_t>& map)
    { PrepareTurn([map](CAIWorker& w) { w.UpdateTerritoryMap(map); }); }
    void StartComputation()
    {
        if (!m_Mailbox) { m_Local->StartComputation(); return; }
        const auto generation = m_Generation, sequence = ++m_Sequence;
        m_Result = m_Mailbox->Submit(Computation(generation, sequence, std::exchange(m_TurnUpdates, {}))).share();
    }
#if defined(WASM_AI_DEFERRED_CAPTURE)
    bool CanDeferCapture() const { return m_Mailbox != nullptr; }
    // The eager updates already queued (pathfinder and territory copies) keep
    // their original read point. captureState queues the game-state update;
    // it is moved ahead of them, as in the original order, before submission.
    void StartComputationDeferred(std::function<void()> captureState)
    {
        const auto generation = m_Generation, sequence = ++m_Sequence;
        auto promise = std::make_shared<std::promise<Result>>();
        m_Result = promise->get_future().share();
        AIDeferredStart::Schedule(this, [this, generation, sequence, promise, captureState = std::move(captureState)](bool run) {
            if (!run)
            {
                promise->set_exception(std::make_exception_ptr(std::runtime_error("AI computation cancelled")));
                return;
            }
            try
            {
                PROFILE2("AI deferred capture");
                auto eager = std::exchange(m_TurnUpdates, {});
                captureState();
                std::move(eager.begin(), eager.end(), std::back_inserter(m_TurnUpdates));
                m_Mailbox->Submit([promise, compute = Computation(generation, sequence, std::exchange(m_TurnUpdates, {}))](CAIWorker& w) {
                    try { promise->set_value(compute(w)); }
                    catch (...) { promise->set_exception(std::current_exception()); }
                });
            }
            catch (...)
            {
                promise->set_exception(std::current_exception());
                throw;
            }
        });
    }
#endif
    void GetCommands(Commands& commands)
    {
        if (!m_Mailbox) { m_Local->GetCommands(commands); return; }
        if (!m_Result.valid()) return;
        const auto& result = m_Result.get();
        if (result.generation != m_Generation || result.sequence != m_Sequence)
            throw std::runtime_error("AI result generation/sequence mismatch");
        commands = result.commands;
    }
    bool CanDefer() const { return m_Mailbox && m_Result.valid(); }
    std::function<std::vector<SimulationCommand>()> DeferredResult()
    {
        const auto result = m_Result;
        const auto generation = m_Generation, sequence = m_Sequence;
        const auto* simulation = m_Simulation;
        const void* owner = this;
        // No actor/component capture: safe even if the AI component is reset.
        // owner is only a key; a destroyed client has cancelled its tasks.
        return [result, generation, sequence, simulation, owner] {
#if defined(WASM_AI_DEFERRED_CAPTURE)
            AIDeferredStart::Run(owner);
#else
            (void)owner;
#endif
            PROFILE2("AI worker result barrier");
            const auto& completed = result.get();
            if (completed.generation != generation || completed.sequence != sequence)
                throw std::runtime_error("Stale AI command batch");
            Script::Request rq(*simulation);
            JS::RootedValue command(rq.cx);
            std::vector<SimulationCommand> commands;
            for (const auto& player : completed.commands)
                for (const auto& clone : player.commands)
                {
                    Script::ReadStructuredClone(rq, clone, &command);
                    commands.emplace_back(player.player, rq.cx, command);
                }
            return commands;
        };
    }
    void Serialize(std::ostream& stream, bool debug)
    {
        // A control message is FIFO behind computation; no actor roots escape.
        stream << Call([debug](CAIWorker& w) { std::ostringstream out; w.Serialize(out, debug); return out.str(); });
    }
    void Deserialize(std::istream& stream, uint32_t players)
    { m_PlayerCount = Call([&stream, players](CAIWorker& w) { w.Deserialize(stream, players); return w.getPlayerSize(); }); }
};

/** Implementation of ICmpAIManager. */
class CCmpAIManager final : public ICmpAIManager
{
public:
	static void ClassInit(CComponentManager&)
	{
	}

	DEFAULT_COMPONENT_ALLOCATOR(AIManager)

	static std::string GetSchema()
	{
		return "<a:component type='system'/><empty/>";
	}

	void Init(const CParamNode&) override
	{
		m_Worker.Init(GetSimContext().GetScriptInterface());

		m_TerritoriesDirtyID = 0;
		m_TerritoriesDirtyBlinkingID = 0;
		m_JustDeserialized = false;
	}

	void Deinit() override
	{
	}

	void Serialize(ISerializer& serialize) override
	{
		serialize.NumberU32_Unbounded("num ais", m_Worker.getPlayerSize());

		// Because the AI worker uses its own Script::Interface, we can't use the
		// ISerializer (which was initialised with the simulation Script::Interface)
		// directly. So we'll just grab the ISerializer's stream and write to it
		// with an independent serializer.

		m_Worker.Serialize(serialize.GetStream(), serialize.IsDebug());
	}

	void Deserialize(const CParamNode& paramNode, IDeserializer& deserialize) override
	{
		Init(paramNode);

		std::uint32_t numAis;
		deserialize.NumberU32_Unbounded("num ais", numAis);
		if (numAis > 0)
			LoadUsedEntityTemplates();

		m_Worker.Deserialize(deserialize.GetStream(), numAis);

		m_JustDeserialized = true;
	}

	void AddPlayer(const std::wstring& id, player_id_t player, std::uint8_t difficulty,
		const std::wstring& behavior) override
	{
		LoadUsedEntityTemplates();

		m_Worker.AddPlayer(id, player, difficulty, behavior);

		// AI players can cheat and see through FoW/SoD, since that greatly simplifies
		// their implementation.
		// (TODO: maybe cleverer AIs should be able to optionally retain FoW/SoD)
		CmpPtr<ICmpRangeManager> cmpRangeManager(GetSystemEntity());
		if (cmpRangeManager)
			cmpRangeManager->SetLosRevealWholeMap(player, true);
	}

	void SetRNGSeed(std::uint32_t seed) override
	{
		m_Worker.SetRNGSeed(seed);
	}

	void TryLoadSharedComponent() override
	{
		m_Worker.TryLoadSharedComponent();
	}

	void RunGamestateInit() override
	{
		const Script::Interface& scriptInterface = GetSimContext().GetScriptInterface();
		Script::Request rq(scriptInterface);

		CmpPtr<ICmpAIInterface> cmpAIInterface(GetSystemEntity());
		ENSURE(cmpAIInterface);

		// Get the game state from AIInterface
		// We flush events from the initialization so we get a clean state now.
		JS::RootedValue state(rq.cx);
		cmpAIInterface->GetFullRepresentation(&state, true);

		// Get the passability data
		Grid<NavcellData> dummyGrid;
		const Grid<NavcellData>* passabilityMap = &dummyGrid;
		CmpPtr<ICmpPathfinder> cmpPathfinder(GetSystemEntity());
		if (cmpPathfinder)
			passabilityMap = &cmpPathfinder->GetPassabilityGrid();

		// Get the territory data
		// Since getting the territory grid can trigger a recalculation, we check NeedUpdateAI first
		Grid<std::uint8_t> dummyGrid2;
		const Grid<std::uint8_t>* territoryMap = &dummyGrid2;
		CmpPtr<ICmpTerritoryManager> cmpTerritoryManager(GetSystemEntity());
		if (cmpTerritoryManager && cmpTerritoryManager->NeedUpdateAI(&m_TerritoriesDirtyID, &m_TerritoriesDirtyBlinkingID))
			territoryMap = &cmpTerritoryManager->GetTerritoryGrid();

		LoadPathfinderClasses(state);
		std::map<std::string, pass_class_t> nonPathfindingPassClassMasks, pathfindingPassClassMasks;
		if (cmpPathfinder)
			cmpPathfinder->GetPassabilityClasses(nonPathfindingPassClassMasks, pathfindingPassClassMasks);

		m_Worker.RunGamestateInit(Script::WriteStructuredClone(rq, state),
			*passabilityMap, *territoryMap, nonPathfindingPassClassMasks, pathfindingPassClassMasks);
	}

	void StartComputation() override
	{
		PROFILE("AI setup");

		const Script::Interface& scriptInterface = GetSimContext().GetScriptInterface();
		Script::Request rq(scriptInterface);

		if (m_Worker.getPlayerSize() == 0)
			return;

		CmpPtr<ICmpAIInterface> cmpAIInterface(GetSystemEntity());
		ENSURE(cmpAIInterface);

		const bool justDeserialized = m_JustDeserialized;
		const auto updateGameState = [this, justDeserialized] {
			Script::Request rq(GetSimContext().GetScriptInterface());
			CmpPtr<ICmpAIInterface> cmpAIInterface(GetSystemEntity());
			ENSURE(cmpAIInterface);

			// Get the game state from AIInterface
			JS::RootedValue state(rq.cx);
			if (justDeserialized)
				cmpAIInterface->GetFullRepresentation(&state, false);
			else
				cmpAIInterface->GetRepresentation(&state);
			LoadPathfinderClasses(state); // add the pathfinding classes to it

			// Update the game state
			m_Worker.UpdateGameState(state);
		};
#if defined(WASM_AI_DEFERRED_CAPTURE)
		// Threaded browser candidate only; the C++ grids below are still read here.
		const bool deferCapture = !justDeserialized && m_Worker.CanDeferCapture();
#else
		const bool deferCapture = false;
#endif
		if (!deferCapture)
			updateGameState();

		// Update the pathfinding data
		CmpPtr<ICmpPathfinder> cmpPathfinder(GetSystemEntity());
		if (cmpPathfinder)
		{
			const GridUpdateInformation& dirtinessInformations = cmpPathfinder->GetAIPathfinderDirtinessInformation();

			if (dirtinessInformations.dirty || m_JustDeserialized)
			{
				const Grid<NavcellData>& passabilityMap = cmpPathfinder->GetPassabilityGrid();

				std::map<std::string, pass_class_t> nonPathfindingPassClassMasks, pathfindingPassClassMasks;
				cmpPathfinder->GetPassabilityClasses(nonPathfindingPassClassMasks, pathfindingPassClassMasks);

				m_Worker.UpdatePathfinder(passabilityMap,
					dirtinessInformations.globallyDirty, dirtinessInformations.dirtinessGrid, m_JustDeserialized,
					nonPathfindingPassClassMasks, pathfindingPassClassMasks);
			}

			cmpPathfinder->FlushAIPathfinderDirtinessInformation();
		}

		// Update the territory data
		// Since getting the territory grid can trigger a recalculation, we check NeedUpdateAI first
		CmpPtr<ICmpTerritoryManager> cmpTerritoryManager(GetSystemEntity());
		if (cmpTerritoryManager && (cmpTerritoryManager->NeedUpdateAI(&m_TerritoriesDirtyID, &m_TerritoriesDirtyBlinkingID) || m_JustDeserialized))
		{
			const Grid<std::uint8_t>& territoryMap = cmpTerritoryManager->GetTerritoryGrid();
			m_Worker.UpdateTerritoryMap(territoryMap);
		}

#if defined(WASM_AI_DEFERRED_CAPTURE)
		if (deferCapture)
			m_Worker.StartComputationDeferred(updateGameState);
		else
#endif
		m_Worker.StartComputation();

		m_JustDeserialized = false;
	}

	void PushCommands() override
	{
		if (m_Worker.CanDefer())
		{
			CmpPtr<ICmpCommandQueue> queue(GetSystemEntity());
			if (queue) queue->PushDeferredLocalCommands(m_Worker.DeferredResult());
			return;
		}
		std::vector<CAIWorker::SCommandSets> commands;
		m_Worker.GetCommands(commands);

		CmpPtr<ICmpCommandQueue> cmpCommandQueue(GetSystemEntity());
		if (!cmpCommandQueue)
			return;

		const Script::Interface& scriptInterface = GetSimContext().GetScriptInterface();
		Script::Request rq(scriptInterface);
		JS::RootedValue clonedCommandVal(rq.cx);

		for (size_t i = 0; i < commands.size(); ++i)
		{
			for (size_t j = 0; j < commands[i].commands.size(); ++j)
			{
				Script::ReadStructuredClone(rq, commands[i].commands[j], &clonedCommandVal);
				cmpCommandQueue->PushLocalCommand(commands[i].player, clonedCommandVal);
			}
		}
	}

private:
	size_t m_TerritoriesDirtyID;
	size_t m_TerritoriesDirtyBlinkingID;

	bool m_JustDeserialized;

	/**
	 * Load the templates of all entities on the map (called when adding a new AI player for a new game
	 * or when deserializing)
	 */
	void LoadUsedEntityTemplates()
	{
		if (m_Worker.HasLoadedEntityTemplates())
			return;

		CmpPtr<ICmpTemplateManager> cmpTemplateManager(GetSystemEntity());
		ENSURE(cmpTemplateManager);

		std::vector<std::string> templateNames = cmpTemplateManager->FindUsedTemplates();
		std::vector<std::pair<std::string, const CParamNode*> > usedTemplates;
		usedTemplates.reserve(templateNames.size());
		for (const std::string& name : templateNames)
		{
			const CParamNode* node = cmpTemplateManager->GetTemplateWithoutValidation(name);
			if (node)
				usedTemplates.emplace_back(name, node);
		}
		// Send the data to the worker
		m_Worker.LoadEntityTemplates(usedTemplates);
	}

	void LoadPathfinderClasses(JS::HandleValue state)
	{
		CmpPtr<ICmpPathfinder> cmpPathfinder(GetSystemEntity());
		if (!cmpPathfinder)
			return;

		const Script::Interface& scriptInterface = GetSimContext().GetScriptInterface();
		Script::Request rq(scriptInterface);

		JS::RootedValue classesVal(rq.cx);
		Script::CreateObject(rq, &classesVal);

		std::map<std::string, pass_class_t> classes;
		cmpPathfinder->GetPassabilityClasses(classes);
		for (std::map<std::string, pass_class_t>::iterator it = classes.begin(); it != classes.end(); ++it)
			Script::SetProperty(rq, classesVal, it->first.c_str(), it->second, true);

		Script::SetProperty(rq, state, "passabilityClasses", classesVal, true);
	}

	CAIWorkerClient m_Worker;
};

REGISTER_COMPONENT_TYPE(AIManager)
