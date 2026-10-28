/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef INCLUDED_SIMKERNELS
#define INCLUDED_SIMKERNELS
// Optional browser candidate (WASM_SIM_KERNELS): exact script replacements for
// the simulation functions that dominate turns in which units are created or
// technologies researched. Each one is installed only if the source of every
// original it replaces or inlines is unchanged. WASM_SIM_KERNEL_VERIFY (diagnostic)
// also runs the original on each call, keeps its result and counts mismatches.
#include <atomic>
#include <emscripten.h>
#include <string>

namespace SimKernels
{
// 0 MatchesClassList, 1 ModifiersManager.OnGlobalOwnershipChanged,
// 2 AIInterface.OnTemplateModification, 3 AIInterface.OnGlobalValueModification,
// 4 ModifiersManager.ApplyModifiers (player-wide part), 5 GetTechModifiedProperty,
// 6 Timer.OnUpdate. Verification counts of the AI worker's kernels add to the same kinds.
inline constexpr int kKinds = 7;
inline std::atomic<int> installed{-1}, aiInstalled{-1};
inline std::atomic<unsigned> verified[kKinds]{}, mismatches[kKinds]{};

inline void Verified(int kind)
{
	if (kind >= 0 && kind < kKinds)
		++verified[kind];
}

inline void Mismatch(int kind)
{
	if (kind >= 0 && kind < kKinds)
		++mismatches[kind];
}

// Evaluated once after the simulation scripts are loaded; returns the bit mask
// of installed kernels.
inline constexpr char Install[] = R"JS(
(function() {
    "use strict";
    // FNV-1a over UTF-16 code units of a function's source text.
    const hash = text => {
        let h = 0x811c9dc5;
        for (let i = 0; i < text.length; ++i)
            h = Math.imul(h ^ text.charCodeAt(i), 0x01000193) >>> 0;
        return h;
    };
    const unchanged = (fn, expected) => typeof fn === "function" && hash(fn.toString()) === expected;
    const verify = !!globalThis.__simKernelVerify;
    const check = (kind, same) => { if (same) Engine.SimKernelVerified(kind); else Engine.SimKernelMismatch(kind); };
    // Bounded memo tables for pure functions of immutable strings.
    const remember = (table, key, value) => {
        if (table.size >= 4096)
            table.clear();
        table.set(key, value);
        return value;
    };
    // Structural equality of the plain data the AIInterface handlers record.
    const same = (a, b) => {
        if (Object.is(a, b))
            return true;
        if (typeof a !== "object" || typeof b !== "object" || !a || !b || Array.isArray(a) !== Array.isArray(b))
            return false;
        const keys = Object.keys(a), other = Object.keys(b);
        if (keys.length !== other.length)
            return false;
        for (let i = 0; i < keys.length; ++i)
            if (keys[i] !== other[i] || !same(a[keys[i]], b[keys[i]]))
                return false;
        return true;
    };
    let installed = 0;

    // MatchesClassList: the same tests in the same order, with each string split
    // once instead of on every call. Splits of a string never change, and the
    // memoized arrays are never exposed.
    if (typeof MatchesClassList === "function" && unchanged(MatchesClassList, 0x620e99d6))
    {
        const original = MatchesClassList;
        const lists = new Map(), groups = new Map();
        // A "+"/space separated group as (negated, class) pairs, flattened.
        const group = text => {
            const tokens = [];
            for (const c of text.split(/[+\s]+/))
            {
                if (c[0] === "!")
                    tokens.push(true, c.substr(1));
                else
                    tokens.push(false, c);
            }
            return remember(groups, text, tokens);
        };
        const fast = function(classes, match)
        {
            if (!match || !classes)
                return undefined;
            if (typeof match === "string")
                match = lists.get(match) || remember(lists, match, match.split(/\s+/));
            for (const sublist of match)
            {
                if (typeof sublist !== "string")
                {
                    if (sublist.every(c => (c[0] === "!" && classes.indexOf(c.substr(1)) === -1) ||
                                           (c[0] !== "!" && classes.indexOf(c) !== -1)))
                        return true;
                    continue;
                }
                const tokens = groups.get(sublist) || group(sublist);
                let all = true;
                // A class passes when it is absent and negated, or present and not negated.
                for (let i = 0; i < tokens.length; i += 2)
                    if ((classes.indexOf(tokens[i + 1]) === -1) !== tokens[i])
                    {
                        all = false;
                        break;
                    }
                if (all)
                    return true;
            }
            return false;
        };
        MatchesClassList = verify ? function(classes, match)
        {
            const expected = original(classes, match);
            check(0, fast(classes, match) === expected);
            return expected;
        } : fast;
        installed |= 1;
    }

    // GetTechModifiedProperty with DoesModificationApply inlined: the same
    // modifications in the same order, the same warnings and results. The state
    // argument, when given, records whether a warning was issued.
    const techUnchanged = typeof GetTechModifiedProperty === "function" &&
        unchanged(GetTechModifiedProperty, 0x51386b81) &&
        unchanged(globalThis.GetTechModifiedProperty_numeric, 0x40d830c9) &&
        unchanged(globalThis.GetTechModifiedProperty_string, 0x534f42c7) &&
        unchanged(globalThis.GetTechModifiedProperty_generic, 0x63958907) &&
        typeof DoesModificationApply === "function" && unchanged(DoesModificationApply, 0x03812145);
    let techModified = null;
    if (techUnchanged)
    {
        const applies = (modification, classes) =>
            !modification.affects || !modification.affects.length || MatchesClassList(classes, modification.affects);
        techModified = (modifications, classes, originalValue, state) =>
        {
            if (!modifications.length)
                return originalValue;
            if (typeof originalValue === "string")
            {
                let value = originalValue;
                for (const modification of modifications)
                {
                    if (!applies(modification, classes))
                        continue;
                    if (modification.replace !== undefined)
                        return modification.replace;
                    if (modification.tokens !== undefined)
                        value = HandleTokens(value, modification.tokens);
                    else
                    {
                        if (state)
                            state.warned = true;
                        warn("GetTechModifiedProperty: string modification format not recognized : " + uneval(modification));
                    }
                }
                return value;
            }
            if (typeof originalValue === "number")
            {
                let multiply = 1;
                let add = 0;
                for (const modification of modifications)
                {
                    if (!applies(modification, classes))
                        continue;
                    if (modification.replace !== undefined)
                        return modification.replace;
                    if (modification.multiply !== undefined)
                        multiply *= modification.multiply;
                    else if (modification.add !== undefined)
                        add += modification.add;
                    else
                    {
                        if (state)
                            state.warned = true;
                        warn("GetTechModifiedProperty: numeric modification format not recognized : " + uneval(modification));
                    }
                }
                return originalValue * multiply + add;
            }
            for (const modification of modifications)
            {
                if (!applies(modification, classes))
                    continue;
                if (!modification.replace)
                {
                    if (state)
                        state.warned = true;
                    warn("GetTechModifiedProperty: modification format not recognized : " + uneval(modification));
                }
                return modification.replace;
            }
            return originalValue;
        };
        const original = GetTechModifiedProperty;
        const fast = (modifications, classes, originalValue) => techModified(modifications, classes, originalValue, null);
        GetTechModifiedProperty = verify ? function(modifications, classes, originalValue)
        {
            const expected = original(modifications, classes, originalValue);
            check(5, same(fast(modifications, classes, originalValue), expected));
            return expected;
        } : fast;
        installed |= 32;
    }

    // ModifiersManager. The modifier storage changes only through MultiKeyMap's
    // AddItem/RemoveItem, which report each change of an item list through
    // ModifiersChanged (count-only changes leave the lists as they were), and is
    // rebuilt on Init/Deserialize. A version per (property, secondary key) and per
    // secondary key, bumped in ModifiersChanged and kept per storage object, thus
    // identifies the stored lists. Results computed from those lists are reused
    // while the version holds. Precondition, which every producer in this mod
    // meets: modification arrays and objects are not mutated after being added
    // (DeriveModificationsFromTech and the cheats build new ones per call).
    const MM = typeof ModifiersManager === "function" && ModifiersManager.prototype;
    const MK = typeof MultiKeyMap === "function" && MultiKeyMap.prototype;
    const storageUnchanged = MK && unchanged(MK.AddItem, 0x583f0869) && unchanged(MK.AddItems, 0xd9d33532) &&
        unchanged(MK.RemoveItem, 0xbd9c6f66) && unchanged(MK.RemoveAllItems, 0xabb43c4d) &&
        unchanged(MK._AddItem, 0xa02f9050) && unchanged(MK._RemoveItem, 0x23b1961d) &&
        unchanged(MK._getItems, 0xf96d0718) && unchanged(MK._getItemsOrInit, 0x1cc13791) &&
        unchanged(MK.GetItems, 0xc68ed396) && unchanged(MK.GetAllItems, 0x875f3eef) &&
        unchanged(MK.Deserialize, 0x8409d030);
    if (MM && storageUnchanged && techModified && unchanged(MM.ModifiersChanged, 0xc8043d9c) &&
        unchanged(MM.Init, 0x1c3986a5) && unchanged(MM.Deserialize, 0x6b24e9df))
    {
        const versions = new WeakMap();
        const versionsOf = storage =>
        {
            let v = versions.get(storage);
            if (!v)
                versions.set(storage, v = { "byProperty": new Map(), "bySecondary": new Map() });
            return v;
        };
        const originalChanged = MM.ModifiersChanged;
        MM.ModifiersChanged = function(propertyName, entity)
        {
            const v = versionsOf(this.modifiersStorage);
            let bySecondary = v.byProperty.get(propertyName);
            if (!bySecondary)
                v.byProperty.set(propertyName, bySecondary = new Map());
            bySecondary.set(entity, (bySecondary.get(entity) || 0) + 1);
            v.bySecondary.set(entity, (v.bySecondary.get(entity) || 0) + 1);
            return originalChanged.apply(this, arguments);
        };
        // Joined classes identify the class list by content; only lists of strings
        // without the separator are keyed.
        const classesKey = classes =>
        {
            if (!Array.isArray(classes))
                return undefined;
            for (let i = 0; i < classes.length; ++i)
                if (typeof classes[i] !== "string" || classes[i].indexOf("\0") !== -1)
                    return undefined;
            return classes.join("\0");
        };
        const isIndex = key => String(key >>> 0) === key && key !== "4294967295";
        const bounded = (table, limit) =>
        {
            if (table.size >= limit)
                table.clear();
            return table;
        };

        // OnGlobalOwnershipChanged, the same messages in the same order:
        // - Dropping an entity's value cache instead of replacing it by an empty Map:
        //   cachedValues is not serialized, and its per-entity maps are only read
        //   through get(), where a missing and an empty map both miss.
        // - Per owner, the properties whose modifications apply to a class list, in
        //   the original's visiting order; a property stops at its first applying
        //   modification, since further matches add nothing.
        if (unchanged(MM.OnGlobalOwnershipChanged, 0x02f53d01) && unchanged(MM.InvalidateCache, 0xa3a578db))
        {
            const original = MM.OnGlobalOwnershipChanged;
            const components = new Map();
            const componentOf = name => components.get(name) || remember(components, name, name.split("/")[0]);
            // The original's fetchPlayerModifiedValueNames, for verification and for
            // stored items that are not plain arrays.
            const reference = (manager, owner, classes, modifiedComponents) =>
            {
                if (!owner)
                    return;
                const playerModifs = manager.modifiersStorage.GetAllItems(owner);
                for (const propertyName in playerModifs)
                {
                    const component = propertyName.split("/")[0];
                    playerModifs[propertyName].forEach(item => item.value.forEach(modif =>
                    {
                        if (!DoesModificationApply(modif, classes))
                            return;
                        if (!modifiedComponents[component])
                            modifiedComponents[component] = new Set();
                        modifiedComponents[component].add(propertyName);
                    }));
                }
            };
            // [propertyName, component] pairs that apply, in visiting order, and
            // whether they may be reused; null for items that are not plain arrays.
            const applying = (manager, owner, classes) =>
            {
                const playerModifs = manager.modifiersStorage.GetAllItems(owner);
                let reusable = true;
                for (const propertyName in playerModifs)
                {
                    const items = playerModifs[propertyName];
                    if (!Array.isArray(items))
                        return null;
                    for (let i = 0; i < items.length; ++i)
                        if (i in items && !Array.isArray(items[i].value))
                            return null;
                    if (isIndex(propertyName))
                        reusable = false;
                }
                const pairs = [];
                for (const propertyName in playerModifs)
                {
                    const items = playerModifs[propertyName];
                    let applies = false;
                    for (let i = 0; i < items.length && !applies; ++i)
                    {
                        if (!(i in items))
                            continue;
                        const value = items[i].value;
                        for (let j = 0; j < value.length; ++j)
                        {
                            if (!(j in value))
                                continue;
                            const affects = value[j].affects;
                            if (!affects || !affects.length || MatchesClassList(classes, affects))
                            {
                                applies = true;
                                break;
                            }
                        }
                    }
                    if (applies)
                        pairs.push(propertyName, componentOf(propertyName));
                }
                return { pairs, reusable };
            };
            // Per storage and owner: { version, byClasses: classesKey -> pairs }.
            const ownerMemo = new WeakMap();
            const pairsFor = (manager, owner, classes) =>
            {
                const storage = manager.modifiersStorage;
                const key = classesKey(classes);
                const version = versionsOf(storage).bySecondary.get(owner) || 0;
                let byOwner = ownerMemo.get(storage);
                if (!byOwner)
                    ownerMemo.set(storage, byOwner = new Map());
                let entry = byOwner.get(owner);
                if (!entry || entry.version !== version)
                    byOwner.set(owner, entry = { "version": version, "byClasses": new Map() });
                if (key !== undefined)
                {
                    const hit = entry.byClasses.get(key);
                    if (hit)
                        return hit;
                }
                const result = applying(manager, owner, classes);
                if (result && result.reusable && key !== undefined)
                    bounded(entry.byClasses, 256).set(key, result.pairs);
                return result && result.pairs;
            };
            MM.OnGlobalOwnershipChanged = function(msg)
            {
                if (Object.hasOwn(this, "InvalidateCache"))
                    return original.call(this, msg);
                if (msg.to == INVALID_PLAYER)
                    return;

                for (const valueCache of this.cachedValues.values())
                    valueCache.delete(msg.entity);

                const cmpIdentity = Engine.QueryInterface(msg.entity, IID_Identity);
                if (!cmpIdentity)
                    return;
                const classes = cmpIdentity.GetClassesList();

                const cmpPlayerManager = Engine.QueryInterface(SYSTEM_ENTITY, IID_PlayerManager);
                const oldOwner = cmpPlayerManager.GetPlayerByID(msg.from);
                const newOwner = cmpPlayerManager.GetPlayerByID(msg.to);

                let modifiedComponents = {};
                let plain = true;
                for (const owner of [oldOwner, newOwner])
                {
                    if (!owner)
                        continue;
                    const pairs = pairsFor(this, owner, classes);
                    if (!pairs)
                    {
                        plain = false;
                        break;
                    }
                    for (let i = 0; i < pairs.length; i += 2)
                    {
                        if (!modifiedComponents[pairs[i + 1]])
                            modifiedComponents[pairs[i + 1]] = new Set();
                        modifiedComponents[pairs[i + 1]].add(pairs[i]);
                    }
                }
                if (!plain || verify)
                {
                    const expected = {};
                    reference(this, oldOwner, classes, expected);
                    reference(this, newOwner, classes, expected);
                    if (verify && plain)
                        check(1, same(Object.keys(modifiedComponents), Object.keys(expected)) &&
                            Object.keys(expected).every(c => same(Array.from(modifiedComponents[c]), Array.from(expected[c]))));
                    modifiedComponents = expected;
                }

                for (const component in modifiedComponents)
                    Engine.PostMessage(msg.entity, MT_ValueModification, { "entities": [msg.entity], "component": component, "valueNames": Array.from(modifiedComponents[component]) });
            };
            installed |= 2;
        }

        // ApplyModifiers: the same caches, sets and results. The player-wide part
        // (FetchModifiedProperty for the owner's player entity) is a function of the
        // owner's stored list for the property, the class list's content and the
        // original value, so it is reused across entities while the list's version
        // holds. Results that issued a warning are not reused, so warnings repeat.
        if (unchanged(MM.ApplyModifiers, 0x85659af6) && unchanged(MM.FetchModifiedProperty, 0xbe13d4ac))
        {
            const original = MM.ApplyModifiers, fetch = MM.FetchModifiedProperty;
            const minusZero = {};
            // Per storage: property -> owner -> { version, byClasses: key -> value key -> result }.
            const fetchMemo = new WeakMap();
            const compute = (storage, classesList, propertyName, originalValue, target, state) =>
            {
                const modifs = storage.GetItems(propertyName, target);
                if (!modifs.length)
                    return originalValue;
                const modifications = [];
                modifs.forEach(item => { modifications.push(item.value); });
                return techModified(modifications.flat(), classesList, originalValue, state);
            };
            const playerFetch = (manager, classesList, propertyName, originalValue, owner) =>
            {
                const storage = manager.modifiersStorage;
                const key = classesKey(classesList);
                if (key === undefined)
                    return fetch.call(manager, classesList, propertyName, originalValue, owner);
                const version = versionsOf(storage).byProperty.get(propertyName)?.get(owner) || 0;
                let byProperty = fetchMemo.get(storage);
                if (!byProperty)
                    fetchMemo.set(storage, byProperty = new Map());
                let byOwner = byProperty.get(propertyName);
                if (!byOwner)
                    byProperty.set(propertyName, byOwner = new Map());
                let entry = byOwner.get(owner);
                if (!entry || entry.version !== version)
                    byOwner.set(owner, entry = { "version": version, "byClasses": new Map() });
                let byValue = entry.byClasses.get(key);
                if (!byValue)
                    bounded(entry.byClasses, 256).set(key, byValue = new Map());
                const valueKey = Object.is(originalValue, -0) ? minusZero : originalValue;
                let result;
                if (byValue.has(valueKey))
                    result = byValue.get(valueKey);
                else
                {
                    const state = { "warned": false };
                    result = compute(storage, classesList, propertyName, originalValue, owner, state);
                    if (!state.warned)
                        bounded(byValue, 64).set(valueKey, result);
                }
                if (verify)
                {
                    const expected = fetch.call(manager, classesList, propertyName, originalValue, owner);
                    check(4, same(result, expected));
                    return expected;
                }
                return result;
            };
            MM.ApplyModifiers = function(propertyName, originalValue, entity)
            {
                if (Object.hasOwn(this, "FetchModifiedProperty"))
                    return original.call(this, propertyName, originalValue, entity);
                let newValue = this.cachedValues.get(propertyName);
                if (newValue !== undefined)
                {
                    newValue = newValue.get(entity);
                    if (newValue !== undefined)
                    {
                        newValue = newValue.get(originalValue);
                        if (newValue !== undefined)
                            return newValue;
                    }
                }

                newValue = originalValue;

                const cmpIdentity = QueryMiragedInterface(entity, IID_Identity);
                if (!cmpIdentity)
                    return originalValue;
                const classesList = cmpIdentity.GetClassesList();

                const ownerPlayer = Engine.QueryInterface(entity, IID_Ownership)?.GetOwner();

                if (ownerPlayer !== undefined && ownerPlayer !== INVALID_PLAYER)
                {
                    const ownerEntity = Engine.QueryInterface(SYSTEM_ENTITY, IID_PlayerManager).GetPlayerByID(ownerPlayer);
                    let pc = this.playerEntitiesCached.get(ownerEntity).get(propertyName);
                    if (!pc)
                        pc = this.playerEntitiesCached.get(ownerEntity).set(propertyName, new Set()).get(propertyName);
                    pc.add(entity);
                    newValue = playerFetch(this, classesList, propertyName, newValue, ownerEntity);
                }
                newValue = fetch.call(this, classesList, propertyName, newValue, entity);
                this.Cache(classesList, propertyName, originalValue, newValue, entity);

                return newValue;
            };
            installed |= 16;
        }
    }

    // Timer.OnUpdate. The original collects the due timers by visiting every timer
    // each turn. Here a heap of (time, id) per Timer instance yields the same ids:
    // a timer's time changes only in SetInterval, when it repeats in OnUpdate, or
    // when Init/Deserialize replace the map (then the heap is rebuilt), and
    // UpdateRepeatTime keeps it. Stale entries are dropped when their time no
    // longer matches. Map order is ascending id order, since ids only grow and
    // existing keys keep their place. The run loop is the original's.
    const TM = typeof Timer === "function" && Timer.prototype;
    if (TM && unchanged(TM.OnUpdate, 0xb43596f9) && unchanged(TM.SetInterval, 0xc54510c1) &&
        unchanged(TM.SetTimeout, 0xb03f46f6) && unchanged(TM.UpdateRepeatTime, 0x5bb7cbc1) &&
        unchanged(TM.CancelTimer, 0x061edeb2) && unchanged(TM.Init, 0x22dec5ea))
    {
        const originalUpdate = TM.OnUpdate, originalInterval = TM.SetInterval;
        // Flat binary min-heap of (time, id) pairs.
        const less = (heap, a, b) => heap[a] < heap[b] || (heap[a] === heap[b] && heap[a + 1] < heap[b + 1]);
        const swap = (heap, a, b) =>
        {
            const t = heap[a], i = heap[a + 1];
            heap[a] = heap[b];
            heap[a + 1] = heap[b + 1];
            heap[b] = t;
            heap[b + 1] = i;
        };
        const push = (heap, time, id) =>
        {
            let k = heap.length;
            heap.push(time, id);
            while (k > 0)
            {
                const parent = ((k / 2 - 1) >> 1) * 2;
                if (!less(heap, k, parent))
                    break;
                swap(heap, k, parent);
                k = parent;
            }
        };
        const popTop = heap =>
        {
            const last = heap.length - 2;
            if (last > 0)
                swap(heap, 0, last);
            heap.length = last;
            let k = 0;
            for (;;)
            {
                const left = k * 2 + 2, right = left + 2;
                let smallest = k;
                if (left < heap.length && less(heap, left, smallest))
                    smallest = left;
                if (right < heap.length && less(heap, right, smallest))
                    smallest = right;
                if (smallest === k)
                    break;
                swap(heap, k, smallest);
                k = smallest;
            }
        };
        const indexes = new WeakMap();
        // Times that are not numbers would compare differently from the original's
        // `<=` in a heap; such a timer turns the heap off for this map.
        const indexOf = timer =>
        {
            let index = indexes.get(timer);
            if (index && index.map === timer.timers)
                return index;
            index = { "map": timer.timers, "heap": [], "usable": timer.timers instanceof Map };
            if (index.usable)
                for (const [id, entry] of timer.timers)
                {
                    if (typeof entry.time !== "number" || typeof id !== "number" || entry.time !== entry.time)
                    {
                        index.usable = false;
                        break;
                    }
                    push(index.heap, entry.time, id);
                }
            indexes.set(timer, index);
            return index;
        };
        const track = (timer, id) =>
        {
            const index = indexes.get(timer);
            if (!index || index.map !== timer.timers || !index.usable)
                return;
            const entry = timer.timers.get(id);
            if (!entry)
                return;
            if (typeof entry.time !== "number" || entry.time !== entry.time)
                index.usable = false;
            else
                push(index.heap, entry.time, id);
        };
        TM.SetInterval = function(ent, iid, funcname, time, repeattime, data)
        {
            const id = originalInterval.apply(this, arguments);
            track(this, id);
            return id;
        };
        const scan = timer =>
        {
            const run = [];
            timer.timers.forEach((entry, id) =>
            {
                if (entry.time <= timer.time)
                    run.push(id);
            });
            return run;
        };
        const due = timer =>
        {
            const index = indexOf(timer);
            if (!index.usable)
                return scan(timer);
            const heap = index.heap, run = [], seen = new Set();
            while (heap.length && heap[0] <= timer.time)
            {
                const time = heap[0], id = heap[1];
                popTop(heap);
                const entry = timer.timers.get(id);
                if (entry && entry.time === time && !seen.has(id))
                {
                    seen.add(id);
                    run.push(id);
                }
            }
            run.sort((a, b) => a - b);
            // Popped entries that are still current stay indexed for later turns.
            for (const id of run)
                push(heap, timer.timers.get(id).time, id);
            return run;
        };
        TM.OnUpdate = function(msg)
        {
            if (Object.hasOwn(this, "SetInterval") || Object.hasOwn(this, "OnUpdate"))
                return originalUpdate.call(this, msg);
            this.turnLength = Math.round(msg.turnLength * 1000);
            this.time += this.turnLength;

            let run = due(this);
            if (verify)
            {
                const expected = scan(this);
                check(6, same(run, expected));
                run = expected;
            }

            for (const id of run)
            {
                const timer = this.timers.get(id);

                // An earlier timer might have cancelled this one, so skip it
                if (!timer)
                    continue;

                // The entity was probably destroyed; clean up the timer
                const timerTargetComponent = Engine.QueryInterface(timer.entity, timer.iid);
                if (!timerTargetComponent)
                {
                    this.timers.delete(id);
                    continue;
                }

                // Diagnostic timing builds name each callback's row (SimTiming.h).
                const timed = globalThis.__simTimingTimerName;
                if (timed)
                    Engine.SimTimingBegin("timer:" + timed(timer.iid) + "." + timer.functionName);
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
                        // Indent the stack trace
                        e.stack.trimRight().replace(/^/mg, '  ') + "\n");
                }
                if (timed)
                    Engine.SimTimingEnd();

                if (!timer.repeatTime)
                {
                    this.timers.delete(id);
                    continue;
                }

                timer.time += timer.repeatTime;
                track(this, id);

                // Add it to the list to get re-executed if it's soon enough
                if (timer.time <= this.time)
                    run.push(id);
            }
        };
        installed |= 64;
    }

    // AIInterface template and value modification handlers. A template name that
    // loaded once always yields the same deep-frozen object (CParamNode caches its
    // script value and the template loader never evicts), so per template manager
    // instance its components and value paths are looked up once. Failed loads are
    // not remembered, so they are retried and logged as in the original.
    const AI = typeof AIInterface === "function" && AIInterface.prototype;
    if (AI && unchanged(AI.OnTemplateModification, 0x215d6429) && unchanged(AI.OnGlobalValueModification, 0xfc491802))
    {
        const originalTemplate = AI.OnTemplateModification, originalValue = AI.OnGlobalValueModification;
        const missing = {};
        // Per template manager: name -> { template, values: valName -> base value or missing }.
        const entriesByManager = new WeakMap();
        // Per template manager and this.templates list: component -> entries with it.
        const indexesByManager = new WeakMap();
        const entryOf = (manager, cache, name) =>
        {
            let entry = cache.get(name);
            if (entry)
                return entry;
            const template = manager.GetTemplateWithoutValidation(name);
            if (!template)
                return undefined;
            entry = { "template": template, "values": new Map() };
            cache.set(name, entry);
            return entry;
        };
        // The original's walk to the base template value.
        const baseValue = (entry, valName) =>
        {
            let value = entry.values.get(valName);
            if (value !== undefined)
                return value;
            const strings = valName.split("/");
            let item = entry.template;
            let ended = true;
            for (const str of strings)
            {
                if (item !== undefined && item[str] !== undefined)
                    item = item[str];
                else
                    ended = false;
            }
            value = ended ? (+item == item ? +item : item) : missing;
            entry.values.set(valName, value);
            return value;
        };
        const entriesFor = manager =>
        {
            let cache = entriesByManager.get(manager);
            if (!cache)
                entriesByManager.set(manager, cache = new Map());
            return cache;
        };
        const round = (valName, value) => valName === "Player/MaxPopulation" || valName === "Cost/Population" ||
            valName === "Population/Bonus" ? Math.round(value) : value;

        const fastTemplate = function(msg)
        {
            const cmpTemplateManager = Engine.QueryInterface(SYSTEM_ENTITY, IID_TemplateManager);
            if (!this.templates)
            {
                this.templates = [];
                for (const templateName of cmpTemplateManager.FindAllTemplates(false))
                {
                    // Remove templates that we obviously don't care about.
                    if (templateName.startsWith("campaigns/") || templateName.startsWith("rubble/") ||
                        templateName.startsWith("skirmish/"))
                        continue;
                    const template = cmpTemplateManager.GetTemplateWithoutValidation(templateName);
                    if (!template || !template.Identity || !template.Identity.Civ)
                        continue;
                    this.templates.push(templateName);
                }
            }
            let byList = indexesByManager.get(cmpTemplateManager);
            if (!byList)
                indexesByManager.set(cmpTemplateManager, byList = new WeakMap());
            let index = byList.get(this.templates);
            if (!index)
                byList.set(this.templates, index = new Map());
            let entries = index.get(msg.component);
            if (!entries)
            {
                const cache = entriesFor(cmpTemplateManager);
                entries = [];
                let complete = true;
                for (const name of this.templates)
                {
                    const entry = entryOf(cmpTemplateManager, cache, name);
                    if (!entry)
                        complete = false;
                    else if (entry.template[msg.component])
                        entries.push([name, entry]);
                }
                // Names that failed to load are retried by the original on every call.
                if (!complete)
                    return originalTemplate.call(this, msg);
                index.set(msg.component, entries);
            }
            for (const [name, entry] of entries)
                for (const valName of msg.valueNames)
                {
                    const oldValue = baseValue(entry, valName);
                    if (oldValue === missing)
                        continue;
                    const newValue = round(valName, ApplyValueModificationsToTemplate(valName, oldValue, msg.player, entry.template));
                    if (newValue == oldValue)
                        continue;
                    if (!this.changedTemplateInfo[msg.player])
                        this.changedTemplateInfo[msg.player] = {};
                    if (!this.changedTemplateInfo[msg.player][name])
                        this.changedTemplateInfo[msg.player][name] = [{ "variable": valName, "value": newValue }];
                    else
                        this.changedTemplateInfo[msg.player][name].push({ "variable": valName, "value": newValue });
                }
        };

        const fastValue = function(msg)
        {
            this.events.ValueModification.push(msg);
            const cmpTemplateManager = Engine.QueryInterface(SYSTEM_ENTITY, IID_TemplateManager);
            const cache = entriesFor(cmpTemplateManager);
            for (const ent of msg.entities)
            {
                const templateName = cmpTemplateManager.GetCurrentTemplateName(ent);
                // if there's no template name, the unit is probably killed, ignore it.
                if (!templateName || !templateName.length)
                    continue;
                const entry = entryOf(cmpTemplateManager, cache, templateName);
                if (!entry || !entry.template[msg.component])
                    continue;
                for (const valName of msg.valueNames)
                {
                    const oldValue = baseValue(entry, valName);
                    if (oldValue === missing)
                        continue;
                    const newValue = round(valName, ApplyValueModificationsToEntity(valName, oldValue, ent));
                    if (newValue == oldValue)
                        continue;
                    if (!this.changedEntityTemplateInfo[ent])
                        this.changedEntityTemplateInfo[ent] = [{ "variable": valName, "value": newValue }];
                    else
                        this.changedEntityTemplateInfo[ent].push({ "variable": valName, "value": newValue });
                }
            }
        };

        // Verification runs the original and the kernel on empty records, keeps the
        // original's and appends it to the real records as the original would have.
        // Value modifiers only cache their results, so the second run sees the same values.
        const append = (target, source, depth) =>
        {
            for (const key in source)
            {
                if (depth && target[key])
                    append(target[key], source[key], depth - 1);
                else if (target[key])
                    target[key].push(...source[key]);
                else
                    target[key] = source[key];
            }
        };
        AI.OnTemplateModification = verify ? function(msg)
        {
            const real = this.changedTemplateInfo;
            this.changedTemplateInfo = {};
            originalTemplate.call(this, msg);
            const expected = this.changedTemplateInfo;
            this.changedTemplateInfo = {};
            fastTemplate.call(this, msg);
            check(2, same(this.changedTemplateInfo, expected));
            this.changedTemplateInfo = real;
            append(real, expected, 1);
        } : fastTemplate;
        AI.OnGlobalValueModification = verify ? function(msg)
        {
            const real = this.changedEntityTemplateInfo, events = this.events.ValueModification;
            this.changedEntityTemplateInfo = {};
            this.events.ValueModification = [];
            originalValue.call(this, msg);
            const expected = this.changedEntityTemplateInfo;
            this.changedEntityTemplateInfo = {};
            fastValue.call(this, msg);
            check(3, same(this.changedEntityTemplateInfo, expected));
            this.changedEntityTemplateInfo = real;
            this.events.ValueModification = events;
            events.push(msg);
            append(real, expected, 0);
        } : fastValue;
        installed |= 12;
    }
    return installed;
})()
)JS";
}

extern "C" EMSCRIPTEN_KEEPALIVE inline const char* Phase45SimKernelStats()
{
	// Only atomic counters; safe to read from the browser thread.
	static std::string result;
	result = "{\"installed\":" + std::to_string(SimKernels::installed.load()) +
		",\"aiInstalled\":" + std::to_string(SimKernels::aiInstalled.load()) + ",\"verified\":[";
	for (int i = 0; i < SimKernels::kKinds; ++i)
		result += (i ? "," : "") + std::to_string(SimKernels::verified[i].load());
	result += "],\"mismatches\":[";
	for (int i = 0; i < SimKernels::kKinds; ++i)
		result += (i ? "," : "") + std::to_string(SimKernels::mismatches[i].load());
	result += "]}";
	return result.c_str();
}
#endif
