// Usage: node wasm/scripts/test-obstruction-kernel.cjs <repo root> [mapModule.js] [gamestate.js]
// Defaults to the workspace copies with LF line endings, which match the packaged public.zip.
// Checks the createObstructionMap guard (ModuleSourceKernels.h) and its wrapper
// (AIMapKernels.h ObstructionInstall) against the original, with a JS mirror of
// AIMapKernels::ObstructionTiles standing in for the native kernel.
"use strict";
const fs = require("fs"), path = require("path"), vm = require("vm");
const [root, modulePathArg, gamestatePathArg] = process.argv.slice(2);
const modulePath = modulePathArg || path.join(root, "binaries/data/mods/public/simulation/ai/petra/mapModule.js");
const gamestatePath = gamestatePathArg || path.join(root, "binaries/data/mods/public/simulation/ai/common-api/gamestate.js");
const moduleText = fs.readFileSync(modulePath, "utf8").replace(/\r\n/g, "\n");
const headerText = file => fs.readFileSync(path.join(root, file), "utf8").replace(/\r\n/g, "\n");
const transformHeader = headerText("source/scriptinterface/ModuleSourceKernels.h");
const kernelsHeader = headerText("source/simulation2/helpers/AIMapKernels.h");

const cString = name => {
    const m = transformHeader.match(new RegExp(name + " =\\s*((?:\\s*\"(?:[^\"\\\\]|\\\\.)*\")+);"));
    return m[1].match(/"((?:[^"\\]|\\.)*)"/g).map(s => JSON.parse(s)).join("");
};
const loop = cString("kObstructionLoop"), guard = cString("kObstructionGuard");
const fnv = bytes => { let h = 0x811c9dc5; for (const c of bytes) h = Math.imul(h ^ c, 0x01000193) >>> 0; return h; };
const expectedHash = parseInt(transformHeader.match(/kMapModuleHash = (0x[0-9a-f]+)u/)[1], 16);
if (fnv(Buffer.from(moduleText, "utf8")) !== expectedHash) throw new Error("module hash differs from kMapModuleHash");
const at = moduleText.indexOf(loop);
if (at < 0 || moduleText.indexOf(loop, at + 1) >= 0) throw new Error("loop not found exactly once");
const transformed = moduleText.slice(0, at + 1) + guard + moduleText.slice(at + 1);
if (transformed.split("\n").length !== moduleText.split("\n").length) throw new Error("line count changed");

const install = kernelsHeader.slice(kernelsHeader.indexOf('ObstructionInstall[] = R"AIJS(') + 'ObstructionInstall[] = R"AIJS('.length);
const installSource = install.slice(0, install.indexOf(')AIJS"'));

// The ally method's hash, as the wrapper checks it.
const gamestate = fs.readFileSync(gamestatePath, "utf8").replace(/\r\n/g, "\n");
const allyText = gamestate.match(/\tisPlayerMutualAlly\(id\)\n\t\{[\s\S]*?\n\t\}/)[0].slice(1);

// JS mirror of AIMapKernels::ObstructionTiles.
function nativeMirror(tiles, territory, tWidth, passability, pWidth, access, checkAccess, accessIndex,
    obstructionMask, ratio, playerID, playerMask, blinkingMask, flags, allies)
{
    const own = !!(flags & 1), ally = !!(flags & 2), neutral = !!(flags & 4), enemy = !!(flags & 8);
    for (let k = 0; k < territory.length; ++k)
    {
        const tilePlayer = territory[k] & playerMask;
        const isConnected = (territory[k] & blinkingMask) === 0;
        if (tilePlayer === playerID) { if (!own || (!neutral && !isConnected)) continue; }
        else if (allies[tilePlayer] === 2) { if (!ally || (!neutral && !isConnected)) continue; }
        else if (tilePlayer === 0) { if (!neutral) continue; }
        else if (!enemy) continue;
        const x = ratio * (k % tWidth), y = ratio * Math.floor(k / tWidth);
        for (let ix = 0; ix < ratio; ++ix)
            for (let iy = 0; iy < ratio; ++iy)
            {
                const i = x + ix + (y + iy) * pWidth;
                if (checkAccess && (i >= access.length || access[i] !== accessIndex)) continue;
                if (i >= passability.length) continue;
                if (!(passability[i] & obstructionMask)) tiles[i] = 255;
            }
    }
    return true;
}

let seed = 4242;
const rand = () => { seed = (Math.imul(seed, 1103515245) + 12345) >>> 0; return seed / 4294967296; };
const pick = a => a[Math.floor(rand() * a.length)];

function makeContext(source, withKernel, verify)
{
    const calls = { ally: 0, kernel: 0 };
    const context = { Uint8Array, Uint16Array, Int32Array, Math, Number, Object, Array, Error, WeakMap, JSON };
    context.globalThis = context;
    context.Engine = {
        AIObstructionTiles: (...args) => { ++calls.kernel; return nativeMirror(...args); },
        AIMapKernelVerified: () => {}
    };
    context.__aiKernelVerify = verify;
    vm.createContext(context);
    if (withKernel)
        vm.runInContext(installSource, context, { filename: "ObstructionInstall" });
    // Module scope stand-ins: imports and the module's own lets.
    const body = source.replace(/^import .*$/mg, "").replace(/^export /mg, "");
    vm.runInContext("var filters = { byClass: c => c }; class InfoMap { constructor(s, t, data) { this.map = data; this.type = t; } setMaxVal(v) { this.maxVal = v; } addInfluence(...a) { (this.influences ||= []).push(a); } };\n" +
        body + "\nglobalThis.createObstructionMap = createObstructionMap;", context, { filename: "mapModule.js" });
    return { context, calls };
}

function scenario()
{
    const tWidth = pick([8, 16, 32]);
    const ratio = pick([1, 2, 4, 8]);
    const pWidth = tWidth * ratio + pick([0, 0, 0, 3, -2]);
    const tData = new Uint8Array(tWidth * pick([tWidth, tWidth, tWidth - 1]));
    for (let k = 0; k < tData.length; ++k)
        tData[k] = pick([0, 0, 1, 1, 2, 3, 4]) | (rand() < 0.15 ? 0x40 : 0) | (rand() < 0.05 ? 0x80 : 0);
    const pLength = Math.max(1, pWidth * (tData.length / tWidth) * ratio + pick([0, 0, -5, 7]));
    const pData = new Uint16Array(pLength);
    for (let i = 0; i < pLength; ++i)
        pData[i] = rand() < 0.3 ? pick([1, 2, 4, 8, 16, 1 << 12]) : 0;
    const land = new Uint16Array(pLength + pick([0, 0, -9]));
    const naval = new Uint16Array(pLength);
    for (let i = 0; i < land.length; ++i) land[i] = pick([1, 1, 2, 3]);
    for (let i = 0; i < naval.length; ++i) naval[i] = pick([0, 5, 6]);
    const mutualAlly = [true, rand() < 0.5, false, rand() < 0.5, false];
    const playerData = { "isMutualAlly": mutualAlly };
    return { tWidth, ratio, pWidth, tData, pData, land, naval, playerData, accessIndex: pick([0, undefined, 1, 2, 3, 2.5]),
        player: pick([1, 2, 3]), template: rand() < 0.2 ? null : {
            placement: pick(["land", "land", "shore"]), own: rand() < 0.8, ally: rand() < 0.5, neutral: rand() < 0.6, enemy: rand() < 0.2 } };
}

function run(made, s)
{
    const { context } = made;
    context.PlayerID = s.player;
    const territoryMap = { data: s.tData, width: s.tWidth, cellSize: 4 * s.ratio };
    const passabilityMap = { data: s.pData, width: s.pWidth, cellSize: 4 };
    // isPlayerMutualAlly from the packaged class body, so the wrapper's hash check applies.
    const GameState = vm.runInContext("(class { " + allyText + " })", context);
    const gameState = new GameState();
    gameState.playerData = s.playerData;
    Object.assign(gameState, {
        getPassabilityMap: () => passabilityMap,
        getPassabilityClassMask: name => name === "building-land" ? 1 | 4 | 16 : 2 | 8,
        ai: { territoryMap, accessibility: { landPassMap: s.land, navalPassMap: s.naval } },
        sharedScript: {}, getOwnStructures: () => ({ filter: () => ({ values: () => [] }) })
    });
    const t = s.template;
    const template = t && {
        buildPlacementType: () => t.placement,
        hasBuildTerritory: kind => t[kind],
        buildDistance: () => undefined
    };
    const map = context.createObstructionMap(gameState, s.accessIndex, template);
    return Array.from(map.map).join(",");
}

let cases = 0, kernelCalls = 0;
for (const verify of [false, true])
    for (let n = 0; n < 3000; ++n)
    {
        const s = scenario();
        const original = makeContext(moduleText, false, false), kernel = makeContext(transformed, true, verify);
        const a = run(original, s), b = run(kernel, s);
        if (a !== b) throw new Error("mismatch in case " + n + " " + JSON.stringify({ ...s, tData: undefined, pData: undefined, land: undefined, naval: undefined }));
        kernelCalls += kernel.calls.kernel;
        ++cases;
    }
console.log("createObstructionMap: " + cases + " cases identical; kernel used in " + kernelCalls);
