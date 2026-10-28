#include <cstdio>
#include <cstring>
#include <jsapi.h>
#include <js/CompilationAndEvaluation.h>
#include <js/Context.h>
#include <js/GCAPI.h>
#include <js/Initialization.h>
#include <js/Realm.h>
#include <js/SourceText.h>

static const JSClass globalClass = {
    "wasm-probe", JSCLASS_GLOBAL_FLAGS, &JS::DefaultGlobalClassOps};

static bool cppDouble(JSContext*, unsigned argc, JS::Value* vp) {
  JS::CallArgs args = JS::CallArgsFromVp(argc, vp);
  if (argc != 1 || !args[0].isInt32() || args[0].toInt32() != 30)
    return false;
  args.rval().setInt32(args[0].toInt32() * 2);
  return true;
}

static bool evaluate(JSContext* cx) {
  JS::RealmOptions options;
  JS::RootedObject global(cx, JS_NewGlobalObject(
      cx, &globalClass, nullptr, JS::FireOnNewGlobalHook, options));
  if (!global) return false;
  JSAutoRealm realm(cx, global);
  if (!JS::InitRealmStandardClasses(cx)) return false;
  if (!JS_DefineFunction(cx, global, "cppDouble", cppDouble, 1, 0)) return false;
  const char* code = "cppDouble([1,2,3,4].reduce((sum, n) => sum + n * n, 0))";
  JS::SourceText<mozilla::Utf8Unit> source;
  if (!source.init(cx, code, std::strlen(code), JS::SourceOwnership::Borrowed))
    return false;
  JS::CompileOptions compileOptions(cx);
  compileOptions.setFileAndLine("probe.js", 1);
  JS::RootedValue result(cx);
  if (!JS::Evaluate(cx, compileOptions, source, &result)) return false;
  if (!result.isInt32() || result.toInt32() != 60) return false;
  JS_GC(cx);
  if (!result.isInt32() || result.toInt32() != 60) return false;
  std::puts("SpiderMonkey WASM: C++/JS round trip = 60; GC passed");
  return true;
}

int main() {
  std::puts("SpiderMonkey WASM: initializing");
  if (!JS_Init()) return 1;
  bool ok = true;
  for (int iteration = 0; iteration < 3 && ok; ++iteration) {
    JSContext* cx = JS_NewContext(64 * 1024 * 1024);
    if (!cx) { ok = false; break; }
    ok = JS::InitSelfHostedCode(cx) && evaluate(cx);
    JS_DestroyContext(cx);
  }
  JS_ShutDown();
  if (ok) std::puts("SpiderMonkey WASM: 3 contexts passed");
  return ok ? 0 : 3;
}
