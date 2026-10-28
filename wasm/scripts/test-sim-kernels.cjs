// Usage: node wasm/scripts/test-sim-kernels.cjs <repo root> [--print-hashes|--fill-header]
// Loads the original public-mod scripts (CRLF normalized to the packaged LF text;
// set PUBMOD to files extracted from public.zip to also check they match) into vm
// contexts, installs SimKernels.h with the computed source hashes, and compares
// every kernel against its original. --fill-header replaces @H_*@ placeholders.
"use strict";
const fs = require("fs"), path = require("path"), vm = require("vm");
const root = process.argv[2];
const mod = path.join(root, "binaries/data/mods/public");
const header = fs.readFileSync(path.join(root, "source/simulation2/helpers/SimKernels.h"), "utf8");
const installSource = header.slice(header.indexOf('R"JS(') + 5, header.indexOf(')JS"'));
// The packaged public.zip has LF line endings; a Windows checkout may have CRLF.
// PUBMOD may point at files extracted from the package's public.zip; they must match.
const read = rel =>
{
    const text = fs.readFileSync(path.join(mod, rel), "utf8").replace(/\r\n/g, "\n");
    if (process.env.PUBMOD && fs.readFileSync(path.join(process.env.PUBMOD, rel), "utf8") !== text)
        throw new Error("workspace and packaged sources differ: " + rel);
    return text;
};
const hash = text => { let h = 0x811c9dc5; for (let i = 0; i < text.length; ++i) h = Math.imul(h ^ text.charCodeAt(i), 0x01000193) >>> 0; return h; };

let seed = 12345;
const rand = () => { seed = (Math.imul(seed, 1103515245) + 12345) >>> 0; return seed / 4294967296; };
const pick = a => a[Math.floor(rand() * a.length)];
const CLASSES = ["Infantry", "Cavalry", "Melee", "Ranged", "Siege", "Ship", "Structure", "Citizen", "Soldier", "Hero", "Champion", "Worker", "Female", "Elephant", "Archer", "Spearman", "CivCentre", "House", "Tower", "Wall", ""];

function makeContext(verify)
{
    const sent = [];
    const components = {};
    const context = {
        console, Map, Set, WeakMap, Math, Object, Array, JSON, Error, String, Number, Symbol,
        warn: m => sent.push(["warn", m]), error: m => sent.push(["error", m]), uneval: JSON.stringify,
        INVALID_PLAYER: -1, INVALID_ENTITY: 0, SYSTEM_ENTITY: 1,
        IID_AIInterface: 9, IID_Timer: 8, IID_Identity: 10, IID_PlayerManager: 11, IID_TemplateManager: 12, IID_ModifiersManager: 13, IID_Ownership: 14, IID_RangeManager: 15, IID_Player: 16,
        MT_ValueModification: 100, MT_TemplateModification: 101,
        __sent: sent, __components: components, __verifyCounts: { ok: [0, 0, 0, 0, 0, 0, 0], bad: [0, 0, 0, 0, 0, 0, 0] },
    };
    context.globalThis = context;
    context.__simKernelVerify = verify;
    context.Engine = {
        RegisterGlobal: (name, value) => { context[name] = value; },
        RegisterSystemComponentType: () => {}, RegisterComponentType: () => {}, RegisterInterface: () => {}, RegisterMessageType: () => {},
        QueryInterface: (ent, iid) => (components[ent] || {})[iid] || null,
        PostMessage: (ent, type, data) => sent.push(["post", ent, type, JSON.stringify(data)]),
        BroadcastMessage: (type, data) => sent.push(["broadcast", type, JSON.stringify(data)]),
        SimKernelVerified: k => context.__verifyCounts.ok[k]++,
        SimKernelMismatch: k => context.__verifyCounts.bad[k]++,
    };
    vm.createContext(context);
    for (const file of ["globalscripts/Templates.js", "globalscripts/Technologies.js", "globalscripts/MultiKeyMap.js",
        "simulation/helpers/ValueModification.js", "simulation/components/ModifiersManager.js", "simulation/components/AIInterface.js", "simulation/components/Timer.js"])
        vm.runInContext(read(file), context, { filename: file });
    // QueryMiragedInterface lives in helpers/Mirage... keep it simple.
    context.QueryMiragedInterface = (ent, iid) => context.Engine.QueryInterface(ent, iid);
    return context;
}

const probe = makeContext(false);
const sources = {
    "@H_MATCHES@": "MatchesClassList",
    "@H_OWNERSHIP@": "ModifiersManager.prototype.OnGlobalOwnershipChanged",
    "@H_INVALIDATE@": "ModifiersManager.prototype.InvalidateCache",
    "@H_DOES_APPLY@": "DoesModificationApply",
    "@H_TEMPLATE@": "AIInterface.prototype.OnTemplateModification",
    "@H_VALUE@": "AIInterface.prototype.OnGlobalValueModification",
    "@H_TECH@": "GetTechModifiedProperty",
    "@H_TECH_NUMERIC@": "GetTechModifiedProperty_numeric",
    "@H_TECH_STRING@": "GetTechModifiedProperty_string",
    "@H_TECH_GENERIC@": "GetTechModifiedProperty_generic",
    "@H_MK_ADDITEM@": "MultiKeyMap.prototype.AddItem",
    "@H_MK_ADDITEMS@": "MultiKeyMap.prototype.AddItems",
    "@H_MK_REMOVEITEM@": "MultiKeyMap.prototype.RemoveItem",
    "@H_MK_REMOVEALL@": "MultiKeyMap.prototype.RemoveAllItems",
    "@H_MK__ADDITEM@": "MultiKeyMap.prototype._AddItem",
    "@H_MK__REMOVEITEM@": "MultiKeyMap.prototype._RemoveItem",
    "@H_MK__GETITEMS@": "MultiKeyMap.prototype._getItems",
    "@H_MK__GETORINIT@": "MultiKeyMap.prototype._getItemsOrInit",
    "@H_MK_GETITEMS@": "MultiKeyMap.prototype.GetItems",
    "@H_MK_GETALL@": "MultiKeyMap.prototype.GetAllItems",
    "@H_MK_DESERIALIZE@": "MultiKeyMap.prototype.Deserialize",
    "@H_CHANGED@": "ModifiersManager.prototype.ModifiersChanged",
    "@H_MM_INIT@": "ModifiersManager.prototype.Init",
    "@H_MM_DESERIALIZE@": "ModifiersManager.prototype.Deserialize",
    "@H_APPLY@": "ModifiersManager.prototype.ApplyModifiers",
    "@H_FETCH@": "ModifiersManager.prototype.FetchModifiedProperty",
    "@H_TIMER_UPDATE@": "Timer.prototype.OnUpdate",
    "@H_TIMER_INTERVAL@": "Timer.prototype.SetInterval",
    "@H_TIMER_TIMEOUT@": "Timer.prototype.SetTimeout",
    "@H_TIMER_REPEAT@": "Timer.prototype.UpdateRepeatTime",
    "@H_TIMER_CANCEL@": "Timer.prototype.CancelTimer",
    "@H_TIMER_INIT@": "Timer.prototype.Init",
};
const hashes = {};
for (const [k, expression] of Object.entries(sources))
    hashes[k] = hash(vm.runInContext(expression + ".toString()", probe));
const hex = v => "0x" + v.toString(16).padStart(8, "0");
if (process.argv.includes("--print-hashes"))
    for (const [k, v] of Object.entries(hashes)) console.log(k, hex(v));
if (process.argv.includes("--fill-header"))
{
    const headerPath = path.join(root, "source/simulation2/helpers/SimKernels.h");
    let text = fs.readFileSync(headerPath, "utf8");
    for (const [k, v] of Object.entries(hashes))
        text = text.split(k).join(hex(v));
    fs.writeFileSync(headerPath, text);
    console.log("header filled");
    process.exit(0);
}
let source = installSource;
for (const [k, v] of Object.entries(hashes))
    source = source.split(k).join(hex(v));
if (/@H_[A-Z_]+@/.test(source))
    throw new Error("unfilled placeholder " + source.match(/@H_[A-Z_]+@/)[0]);

function install(context)
{
    return vm.runInContext(source, context, { filename: "SimKernels.h" });
}

// ---- MatchesClassList ----
function randomGroup()
{
    const n = 1 + Math.floor(rand() * 3);
    const parts = [];
    for (let i = 0; i < n; ++i) parts.push((rand() < 0.25 ? "!" : "") + pick(CLASSES));
    const seps = ["+", " ", "+ ", "  ", "++"];
    let s = parts[0];
    for (let i = 1; i < n; ++i) s += pick(seps) + parts[i];
    if (rand() < 0.05) s = " " + s;
    if (rand() < 0.05) s = s + " ";
    return s;
}
function randomMatch()
{
    const r = rand();
    if (r < 0.03) return pick([undefined, null, "", 0]);
    if (r < 0.4)
    {
        const n = 1 + Math.floor(rand() * 3);
        const groups = [];
        for (let i = 0; i < n; ++i) groups.push(randomGroup());
        return groups.join(pick([" ", "  "]));
    }
    const n = Math.floor(rand() * 4);
    const out = [];
    for (let i = 0; i < n; ++i)
        out.push(rand() < 0.15 ? Array.from({ length: 1 + Math.floor(rand() * 2) }, () => (rand() < 0.2 ? "!" : "") + pick(CLASSES)) : randomGroup());
    return out;
}
function randomClasses()
{
    if (rand() < 0.03) return pick([undefined, null]);
    const n = Math.floor(rand() * 8);
    const out = [];
    for (let i = 0; i < n; ++i) out.push(pick(CLASSES));
    if (rand() < 0.1) return out.join(" ");
    return out;
}
{
    const original = makeContext(false), kernel = makeContext(false);
    const mask = install(kernel);
    if (!(mask & 1)) throw new Error("MatchesClassList kernel not installed, mask " + mask);
    let n = 0;
    for (let i = 0; i < 300000; ++i)
    {
        const classes = randomClasses(), match = randomMatch();
        const a = original.MatchesClassList(classes, match), b = kernel.MatchesClassList(classes, match);
        if (!Object.is(a, b)) throw new Error("MatchesClassList mismatch " + JSON.stringify([classes, match, a, b]));
        ++n;
    }
    console.log("MatchesClassList: " + n + " cases equal; install mask " + mask);
}

// ---- ModifiersManager + AIInterface ----
function setupWorld(context, worldSeed, shared)
{
    seed = worldSeed;
    const C = context.__components;
    const templates = {};
    const names = [];
    const deepFreeze = o => { if (o && typeof o === "object") { Object.freeze(o); for (const k of Object.keys(o)) deepFreeze(o[k]); } return o; };
    for (let i = 0; i < 120; ++i)
    {
        const name = pick(["units/", "structures/", "campaigns/", "skirmish/", "rubble/", "other/"]) + "t" + i;
        names.push(name);
        if (rand() < 0.03) { templates[name] = null; continue; }
        const classes = Array.from({ length: 1 + Math.floor(rand() * 4) }, () => pick(CLASSES.slice(0, -1)));
        const t = { "Identity": { "Classes": { "_string": classes.join(" ") } } };
        if (rand() < 0.9) t.Identity.Civ = pick(["athen", "brit", "gaia"]);
        if (rand() < 0.3) t.Identity.Rank = pick(["Basic", "Elite"]);
        if (rand() < 0.6) t.Attack = { "Melee": { "Hack": String(Math.floor(rand() * 10)), "Pierce": "2" }, "Ranged": rand() < 0.5 ? { "Pierce": "6" } : undefined };
        if (rand() < 0.8) t.Cost = { "Resources": { "food": String(Math.floor(rand() * 100)), "wood": "20" }, "Population": "1" };
        if (rand() < 0.5) t.Health = { "Max": String(100 + Math.floor(rand() * 100)) };
        if (rand() < 0.2) t.Player = { "MaxPopulation": "200" };
        if (rand() < 0.2) t.Population = { "Bonus": "5" };
        if (rand() < 0.3) t.VisualActor = { "Actor": "a.xml" };
        templates[name] = deepFreeze(JSON.parse(JSON.stringify(t)));
    }
    const entityTemplate = {};
    const templateManager = {
        FindAllTemplates: () => names.slice(),
        GetTemplateWithoutValidation: n => templates[n] === undefined ? null : templates[n],
        GetCurrentTemplateName: e => entityTemplate[e] || "",
    };
    const playerEntities = { "0": 2, "1": 3, "2": 4 };
    const playerManager = { GetPlayerByID: id => (id in playerEntities ? playerEntities[id] : 0) };
    const ownerOf = {};
    C[1] = { [context.IID_TemplateManager]: templateManager, [context.IID_PlayerManager]: playerManager };
    const mm = new context.ModifiersManager();
    mm.Init();
    C[1][context.IID_ModifiersManager] = mm;
    const ai = new context.AIInterface();
    ai.Init();
    // Player entities.
    for (const p of [0, 1, 2]) mm.OnGlobalPlayerEntityChanged({ "from": -1, "to": playerEntities[p] });
    for (let e = 10; e < 70; ++e)
    {
        const candidates = names.filter(n => templates[n] && n.startsWith("units/")).slice(0, shared ? 3 : undefined);
        entityTemplate[e] = rand() < 0.05 ? "" : pick(candidates.length ? candidates : names);
        const t = templates[entityTemplate[e]];
        const classes = t ? context.GetIdentityClasses(t.Identity) : [];
        ownerOf[e] = Math.floor(rand() * 3);
        C[e] = { [context.IID_Identity]: { GetClassesList: () => classes }, [context.IID_Ownership]: { GetOwner: () => ownerOf[e] } };
    }
    return { mm, ai, names, templates, entityTemplate, playerEntities, ownerOf };
}
const PROPS = ["Attack/Melee/Hack", "Attack/Melee/Pierce", "Attack/Ranged/Pierce", "Cost/Resources/food", "Cost/Population", "Health/Max", "Player/MaxPopulation", "Population/Bonus", "VisualActor/Actor", "Missing/Value"];
function randomModification()
{
    const m = {};
    const r = rand();
    if (r < 0.5) m.multiply = pick([0.8, 1.1, 1.25, 2]);
    else if (r < 0.9) m.add = pick([1, 2, -1, 5]);
    else if (r < 0.95) m.replace = pick([3, 7, -0, "x"]);
    else m.tokens = pick(["a", "-b", "c>d", "e f"]);
    if (rand() < 0.75) m.affects = rand() < 0.3 ? randomGroup() : [randomGroup(), ...(rand() < 0.3 ? [randomGroup()] : [])];
    return m;
}
function randomOperations(count, opsSeed)
{
    seed = opsSeed;
    const ops = [];
    for (let i = 0; i < count; ++i)
    {
        const r = rand();
        if (r < 0.3)
        {
            const mods = {};
            for (let k = 0; k < 1 + Math.floor(rand() * 3); ++k) mods[pick(PROPS)] = Array.from({ length: 1 + Math.floor(rand() * 2) }, randomModification);
            ops.push(["add", "tech" + Math.floor(rand() * 20), mods, pick([2, 3, 4, 10 + Math.floor(rand() * 60)])]);
        }
        else if (r < 0.4) ops.push(["remove", "tech" + Math.floor(rand() * 20), pick([2, 3, 4])]);
        else if (r < 0.65) ops.push(["owner", 10 + Math.floor(rand() * 60), pick([-1, 0, 1, 2])]);
        else if (r < 0.8) ops.push(["apply", pick(PROPS), pick([1, 5, 10, 100, 0, -0, NaN, "a b", "c", 2.5]), 10 + Math.floor(rand() * 60)]);
        else if (r < 0.9) ops.push(["template", pick([0, 1, 2]), pick(PROPS)]);
        else ops.push(["value", Array.from({ length: 1 + Math.floor(rand() * 8) }, () => 10 + Math.floor(rand() * 62)), pick(PROPS)]);
    }
    return ops;
}
function run(context, worldSeed, ops, shared)
{
    const w = setupWorld(context, worldSeed, shared);
    const results = [];
    for (const op of ops)
    {
        switch (op[0])
        {
        case "add": w.mm.AddModifiers(op[1], op[2], op[3]); break;
        case "remove": w.mm.RemoveAllModifiers(op[1], op[2]); break;
        case "owner":
        {
            const from = w.ownerOf[op[1]];
            w.ownerOf[op[1]] = op[2];
            w.mm.OnGlobalOwnershipChanged({ "entity": op[1], "from": from, "to": op[2] });
            break;
        }
        case "apply": results.push(w.mm.ApplyModifiers(op[1], op[2], op[3])); break;
        case "template":
        {
            const prop = op[2];
            w.ai.OnTemplateModification({ "player": op[1], "component": prop.split("/")[0], "valueNames": [prop] });
            break;
        }
        case "value":
            w.ai.OnGlobalValueModification({ "entities": op[1], "component": op[2].split("/")[0], "valueNames": [op[2]] });
            break;
        }
    }
    const ai = {}; for (const k of Object.keys(w.ai)) if (k !== "templates") ai[k] = w.ai[k];
    const sent = context.__verifyWarnings === false ? context.__sent.filter(s => s[0] !== "warn") : context.__sent;
    const exact = (k, v) => Object.is(v, -0) ? "<-0>" : (typeof v === "number" && isNaN(v) ? "<NaN>" : v);
    return JSON.stringify({ results: JSON.stringify(results, exact), sent, ai, players: [...w.mm.playerEntitiesCached.keys()], storage: w.mm.modifiersStorage.Serialize() });
}
for (const verify of [false, true])
{
    let worlds = 0;
    for (let world = 1; world <= 60; ++world)
    {
        const ops = randomOperations(400, world * 7919);
        const a = makeContext(false), b = makeContext(verify);
        if (verify) a.__verifyWarnings = b.__verifyWarnings = false;
        const mask = install(b);
        if (mask !== 127) throw new Error("not all kernels installed: " + mask);
        const ra = run(a, world, ops), rb = run(b, world, ops);
        if (ra !== rb)
        {
            let i = 0; while (ra[i] === rb[i]) ++i;
            throw new Error("world " + world + " differs at " + i + ":\n" + ra.slice(Math.max(0, i - 200), i + 200) + "\n---\n" + rb.slice(Math.max(0, i - 200), i + 200));
        }
        if (verify && b.__verifyCounts.bad.some(x => x)) throw new Error("verify mismatches " + JSON.stringify(b.__verifyCounts));
        if (verify && world === 60) console.log("verify counts", JSON.stringify(b.__verifyCounts));
        ++worlds;
    }
    console.log((verify ? "verify mode: " : "kernel mode: ") + worlds + " worlds x 400 operations identical");
}

// AI-like context: only global scripts, so only MatchesClassList installs.
{
    const context = { console, Map, Set, WeakMap, Math, Object, Array, JSON, Error, String, Number, Symbol, Engine: {} };
    context.globalThis = context;
    vm.createContext(context);
    for (const file of ["globalscripts/Templates.js", "globalscripts/Technologies.js"])
        vm.runInContext(read(file), context, { filename: file });
    const mask = install(context);
    if (mask !== 33) throw new Error("AI-like install mask " + mask);
    console.log("AI-like context: install mask " + mask);
}

// Diagnostic FunctionPatch (SimTiming.h) on top of the kernels: same results.
{
    const timing = fs.readFileSync(path.join(root, "source/simulation2/helpers/SimTiming.h"), "utf8").replace(/\r\n/g, "\n");
    const start = timing.indexOf('FunctionPatch[] = R"JS(') + 'FunctionPatch[] = R"JS('.length;
    const patch = timing.slice(start, timing.indexOf(')JS"', start));
    let worlds = 0, wrappedCount = 0;
    for (let world = 1; world <= 20; ++world)
    {
        const ops = randomOperations(400, world * 7919);
        const a = makeContext(false), b = makeContext(false);
        let depth = 0;
        b.Engine.SimTimingBegin = () => ++depth;
        b.Engine.SimTimingEnd = () => --depth;
        if (install(b) !== 127) throw new Error("kernels not installed");
        wrappedCount = vm.runInContext(patch, b, { filename: "FunctionPatch" });
        const ra = run(a, world, ops), rb = run(b, world, ops);
        if (ra !== rb) throw new Error("FunctionPatch changed results in world " + world);
        if (depth !== 0) throw new Error("unbalanced timing scopes " + depth);
        ++worlds;
    }
    console.log("FunctionPatch: " + wrappedCount + " functions wrapped, " + worlds + " worlds identical");
}

// Stress: few templates (shared class lists) and many modifier changes between reads.
{
    let worlds = 0;
    for (const verify of [false, true])
        for (let world = 101; world <= 130; ++world)
        {
            const ops = randomOperations(1500, world * 104729);
            const a = makeContext(false), b = makeContext(verify);
            if (verify) a.__verifyWarnings = b.__verifyWarnings = false;
            if (install(b) !== 127) throw new Error("kernels not installed");
            const ra = run(a, world, ops, true), rb = run(b, world, ops, true);
            if (ra !== rb) throw new Error("shared-template world " + world + " differs (verify " + verify + ")");
            if (b.__verifyCounts.bad.some(x => x)) throw new Error("verify mismatches " + JSON.stringify(b.__verifyCounts));
            if (verify && world === 130) console.log("stress verify counts", JSON.stringify(b.__verifyCounts));
            ++worlds;
        }
    console.log("shared-template stress: " + worlds + " worlds x 1500 operations identical");
}

// Timer kernel: random schedules; callbacks schedule, cancel, change repeat times,
// throw, or lose their target; the map is replaced once as on deserialization.
function runTimers(context, seedValue)
{
    seed = seedValue;
    const log = [];
    const C = context.__components;
    const timer = new context.Timer();
    timer.Init();
    C[1] = { [context.IID_Timer]: timer };
    const IID_T = 77;
    const alive = new Set();
    const target = e => ({
        "Tick": (data, late) => { log.push(["tick", e, data, late]); act(); },
        "Boom": () => { log.push(["boom", e]); throw new Error("boom " + e); }
    });
    for (let e = 2; e < 30; ++e) { C[e] = { [IID_T]: target(e) }; alive.add(e); }
    const act = () =>
    {
        const r = rand();
        const ent = 2 + Math.floor(rand() * 28);
        if (r < 0.15)
            timer.SetTimeout(ent, IID_T, rand() < 0.08 ? "Boom" : "Tick", pick([0, 0, 50, 199.5, 200, 400, 1000]), Math.floor(rand() * 100));
        else if (r < 0.27)
            timer.SetInterval(ent, IID_T, "Tick", pick([0, 100, 333.3, 800]), pick([0, 100, 200, 250.25, 1000]), Math.floor(rand() * 100));
        else if (r < 0.34)
            timer.CancelTimer(1 + Math.floor(rand() * Math.max(1, timer.id)));
        else if (r < 0.40)
            timer.UpdateRepeatTime(1 + Math.floor(rand() * Math.max(1, timer.id)), pick([0, 50, 200, 1000]));
        else if (r < 0.43)
        {
            if (alive.has(ent)) { delete C[ent]; alive.delete(ent); }
            else { C[ent] = { [IID_T]: target(ent) }; alive.add(ent); }
        }
    };
    for (let i = 0; i < 60; ++i)
        act();
    for (let turn = 0; turn < 400; ++turn)
    {
        for (let k = 0; k < 3; ++k)
            act();
        if (turn === 200)
            timer.timers = new Map(timer.timers);
        timer.OnUpdate({ "turnLength": pick([0.2, 0.2, 0.2, 0.35, 0.05]) });
        log.push(["turn", timer.time, timer.timers.size]);
    }
    // Stack traces name the replaced function; the rest of each error must match.
    const errors = context.__sent.map(s => s[0] === "error" ? ["error", s[1].split("\n")[0]] : s);
    return JSON.stringify(log) + JSON.stringify([...timer.timers]) + JSON.stringify(errors);
}
{
    let worlds = 0;
    for (const verify of [false, true])
        for (let world = 1; world <= 40; ++world)
        {
            const a = makeContext(false), b = makeContext(verify);
            if (install(b) !== 127) throw new Error("kernels not installed");
            const ra = runTimers(a, world * 31337), rb = runTimers(b, world * 31337);
            if (ra !== rb)
            {
                let i = 0; while (ra[i] === rb[i]) ++i;
                throw new Error("timer world " + world + " differs at " + i + ":\n" + ra.slice(Math.max(0, i - 300), i + 200) + "\n---\n" + rb.slice(Math.max(0, i - 300), i + 200));
            }
            if (b.__verifyCounts.bad.some(x => x)) throw new Error("timer verify mismatches " + JSON.stringify(b.__verifyCounts));
            if (verify && world === 40) console.log("timer verify counts", JSON.stringify(b.__verifyCounts));
            ++worlds;
        }
    console.log("Timer: " + worlds + " worlds x 400 turns identical");
}
