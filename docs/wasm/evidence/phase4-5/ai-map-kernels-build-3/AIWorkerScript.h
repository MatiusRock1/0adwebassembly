/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef INCLUDED_AIWORKERSCRIPT
#define INCLUDED_AIWORKERSCRIPT

// Scripts embedded in the executable so frozen public.zip remains immutable.
// Capture only on the simulation thread, at the original AI boundary.
inline constexpr char AIWorkerCapture[] = R"AIJS(
globalThis.__captureAIWorkerSnapshot = function() {
    const entities = Object.create(null);
    for (const id of Engine.GetEntitiesWithInterface(IID_AIProxy))
        entities[id] = {};
    // Enumerate each component's existing owners, rather than querying three
    // absent components on every tree, decoration and other AI proxy.
    for (const id of Engine.GetEntitiesWithInterface(IID_UnitAI)) {
        const value = entities[id];
        if (!value) continue;
        const unit = Engine.QueryInterface(id, IID_UnitAI);
        if (unit) value.orders = unit.GetOrders();
    }
    for (const id of Engine.GetEntitiesWithInterface(IID_ResourceSupply)) {
        const value = entities[id];
        if (!value) continue;
        const supply = Engine.QueryInterface(id, IID_ResourceSupply);
        if (supply) value.supply = {amount: supply.GetCurrentAmount(), gatherers: supply.GetNumGatherers()};
    }
    for (const id of Engine.GetEntitiesWithInterface(IID_ResourceGatherer)) {
        const value = entities[id];
        if (!value) continue;
        const gatherer = Engine.QueryInterface(id, IID_ResourceGatherer);
        if (gatherer) value.carrying = gatherer.GetCarryingStatus();
    }
    const players = Object.create(null);
    for (const id of Engine.QueryInterface(SYSTEM_ENTITY, IID_PlayerManager).GetAllPlayers()) {
        const tech = QueryPlayerIDInterface(id, IID_TechnologyManager);
        if (tech) players[id] = {classCounts: tech.classCounts,
            typeCountsByClass: tech.typeCountsByClass, researched: tech.GetResearchedTechs()};
    }
    return {entities, players, requirements: {
        all: RequirementsHelper.AllRequirementsMet.toString(),
        any: RequirementsHelper.AnyRequirementsMet.toString(),
        met: RequirementsHelper.AreRequirementsMet.toString()}};
};
)AIJS";

// Optional compact supply payload. Same owner-thread reads and capture boundary;
// one owned Float64Array replaces thousands of nested cloned supply objects.
inline constexpr char AIWorkerCaptureDense[] = R"AIJS(
globalThis.__captureAIWorkerSnapshot = function() {
    const entities = Object.create(null);
    for (const id of Engine.GetEntitiesWithInterface(IID_AIProxy)) entities[id] = {};
    for (const id of Engine.GetEntitiesWithInterface(IID_UnitAI)) {
        const value = entities[id];
        if (!value) continue;
        const unit = Engine.QueryInterface(id, IID_UnitAI);
        if (unit) value.orders = unit.GetOrders();
    }
    const ids = Engine.GetEntitiesWithInterface(IID_ResourceSupply);
    const supplies = new Float64Array(ids.length * 2);
    for (let i = 0; i < ids.length; ++i) {
        const id = ids[i], value = entities[id];
        if (!value) continue;
        const supply = Engine.QueryInterface(id, IID_ResourceSupply);
        if (!supply) continue;
        const amount = supply.GetCurrentAmount(), gatherers = supply.GetNumGatherers();
        if (typeof amount !== 'number' || typeof gatherers !== 'number') {
            value.supply = {amount, gatherers};
            continue;
        }
        value.supplyIndex = i;
        supplies[2*i] = amount; supplies[2*i+1] = gatherers;
    }
    for (const id of Engine.GetEntitiesWithInterface(IID_ResourceGatherer)) {
        const value = entities[id];
        if (!value) continue;
        const gatherer = Engine.QueryInterface(id, IID_ResourceGatherer);
        if (gatherer) value.carrying = gatherer.GetCarryingStatus();
    }
    const players = Object.create(null);
    for (const id of Engine.QueryInterface(SYSTEM_ENTITY, IID_PlayerManager).GetAllPlayers()) {
        const tech = QueryPlayerIDInterface(id, IID_TechnologyManager);
        if (tech) players[id] = {classCounts: tech.classCounts,
            typeCountsByClass: tech.typeCountsByClass, researched: tech.GetResearchedTechs()};
    }
    return {entities, players, supplies, requirements: {
        all: RequirementsHelper.AllRequirementsMet.toString(),
        any: RequirementsHelper.AnyRequirementsMet.toString(),
        met: RequirementsHelper.AreRequirementsMet.toString()}};
};
)AIJS";

// This context has no simulation globals or C++ component references. Unknown
// component access fails explicitly instead of falling back to live state.
inline constexpr char AIWorkerInstall[] = R"AIJS(
globalThis.__aiSnapshot = {entities: {}, players: {}};
globalThis.__aiEffects = [];
globalThis.__aiAllowEffects = false;
globalThis.Sim = {
    SYSTEM_ENTITY: 0, IID_UnitAI: 'UnitAI', IID_ResourceSupply: 'ResourceSupply',
    IID_ResourceGatherer: 'ResourceGatherer', IID_ModifiersManager: 'ModifiersManager'
};
globalThis.IID_TechnologyManager = 'TechnologyManager';
globalThis.QueryPlayerIDInterface = function(id, iid) {
    if (iid !== IID_TechnologyManager) throw new Error('Unsupported AI player component: ' + iid);
    const tech = __aiSnapshot.players[id];
    return tech && {classCounts: tech.classCounts, typeCountsByClass: tech.typeCountsByClass,
        IsTechnologyResearched: name => tech.researched.has(name)};
};
globalThis.SimEngine = {QueryInterface(id, iid) {
    if (id === Sim.SYSTEM_ENTITY && iid === Sim.IID_ModifiersManager)
        return {AddModifiers(...args) {
            if (!__aiAllowEffects) throw new Error('AI simulation effects outside initialization');
            __aiEffects.push(args);
        }};
    const entity = __aiSnapshot.entities[id];
    if (iid === Sim.IID_UnitAI)
        return entity && Object.hasOwn(entity, 'orders') ? {GetOrders: () => entity.orders} : null;
    if (iid === Sim.IID_ResourceSupply) {
        if (entity?.supply) return {GetCurrentAmount: () => entity.supply.amount,
            GetNumGatherers: () => entity.supply.gatherers};
        if (entity && Object.hasOwn(entity, 'supplyIndex')) {
            const offset = 2 * entity.supplyIndex, values = __aiSnapshot.supplies;
            return {GetCurrentAmount: () => values[offset], GetNumGatherers: () => values[offset+1]};
        }
        return null;
    }
    if (iid === Sim.IID_ResourceGatherer)
        return entity && Object.hasOwn(entity, 'carrying') ? {GetCarryingStatus: () => entity.carrying} : null;
    throw new Error('Unsupported AI snapshot component: ' + iid);
}};
globalThis.__installAIWorkerSnapshot = function(snapshot) {
    __aiSnapshot = snapshot;
    if (!Sim.RequirementsHelper) {
        Sim.RequirementsHelper = {
            AllRequirementsMet: (0, eval)('(' + snapshot.requirements.all + ')'),
            AnyRequirementsMet: (0, eval)('(' + snapshot.requirements.any + ')'),
            AreRequirementsMet: (0, eval)('(' + snapshot.requirements.met + ')')
        };
    }
};
)AIJS";

inline constexpr char AIWorkerApplyEffects[] = R"AIJS(
for (const args of __aiWorkerEffects)
    Engine.QueryInterface(SYSTEM_ENTITY, IID_ModifiersManager).AddModifiers(...args);
globalThis.__aiWorkerEffects = undefined;
)AIJS";
#endif
