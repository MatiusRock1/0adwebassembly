// CPU-only checks for the separately compiled original SpiderMonkey VM.
#include <cstdio>
#include <cstring>
#include <jsapi.h>
#include <js/CompilationAndEvaluation.h>
#include <js/Context.h>
#include <js/GCAPI.h>
#include <js/Initialization.h>
#include <js/Realm.h>
#include <js/SliceBudget.h>
#include <js/SourceText.h>

static const JSClass globalClass = {
    "portable-vm-check", JSCLASS_GLOBAL_FLAGS, &JS::DefaultGlobalClassOps};
static bool collect(JSContext* cx, unsigned argc, JS::Value* vp)
{
    JS_GC(cx);
    JS::CallArgsFromVp(argc,vp).rval().setUndefined();
    return true;
}
static unsigned incrementalYields=0;
static bool collectSlice(JSContext* cx, unsigned argc, JS::Value* vp)
{
    const js::SliceBudget budget(js::TimeBudget(0));
    if (JS::IsIncrementalGCInProgress(cx))
        JS::IncrementalGCSlice(cx,JS::GCReason::API,budget);
    else
    {
        JS::PrepareForFullGC(cx);
        JS::StartIncrementalGC(cx,JS::GCOptions::Normal,JS::GCReason::API,budget);
    }
    if (JS::IsIncrementalGCInProgress(cx)) ++incrementalYields;
    JS::CallArgsFromVp(argc,vp).rval().setUndefined();
    return true;
}
static bool nativeShort(JSContext*, unsigned argc, JS::Value* vp)
{
    auto args=JS::CallArgsFromVp(argc,vp);
    args.rval().setInt32(int(argc)*100+(argc && args[0].isInt32()?args[0].toInt32():0));
    return true;
}
struct Case { const char* name; const char* code; };
static const Case cases[] = {
    {"property-and-call-ICs", R"JS((()=>{
      const object={a:1,b:2}; function add(o,k){return o.a+o[k];}
      let total=0;for(let i=0;i<5000;i++)total+=add(object,'b');
      object.a=7;delete object.b;Object.setPrototypeOf(object,{b:8});
      const ordered=[{k:3},{k:1},{k:2}].sort((a,b)=>a.k-b.k);
      return total===15000 && add(object,'b')===15 && ordered.map(x=>x.k).join('')==='123';
    })())JS"},
    {"exception-unwind-finally", R"JS((()=>{
      let total=0;for(let i=0;i<50;i++)try{try{throw i;}finally{total++;}}catch(e){total+=e;}
      function deep(n){try{return n?deep(n-1):11;}finally{if(n===3)collect();}}
      return total===1275 && deep(20)===11;
    })())JS"},
    {"typed-arrays-and-number-bits", R"JS((()=>{
      const a=new Int32Array([2147483647,2147483648,-2147483649]);
      const f=new Float32Array([1/3,-0,Infinity,NaN]);
      return a.join(',')==='2147483647,-2147483648,2147483647' &&
        f[0]===Math.fround(1/3) && 1/f[1]===-Infinity && f[2]===Infinity &&
        Number.isNaN(f[3]) && Math.imul(0x7fffffff,2)===-2;
    })())JS"},
    {"live-roots-and-sort-native-callback", R"JS((()=>{
      const root={items:Array.from({length:128},(_,i)=>({value:'kept-'+i,index:i}))};
      collect();let collected=false;
      root.items.sort((a,b)=>{if(!collected){collected=true;collect();}return b.index-a.index;});
      collect();
      return root.items[0].value==='kept-127' && root.items[127].value==='kept-0' &&
        root.items.reduce((sum,item)=>sum+item.index,0)===8128;
    })())JS"},
    {"collecting-getters-and-property-fallbacks", R"JS((()=>{
      function read(object){return object.value.index;}
      let total=0,expected=0,collections=0;
      for(let round=0;round<32;round++){
        let needsGC=true;
        const prototype={get value(){
          if(needsGC){needsGC=false;collections++;collect();}
          return this.payload;
        }};
        for(let i=0;i<64;i++){
          const object=Object.create(prototype);
          object['shape'+((round+i)%17)]=i;
          object.payload={index:round*64+i,kept:'root-'+i};
          // Mix proxy/getter and own-slot paths at the same hot callsite.
          const input=i%7===0?new Proxy(object,{}):object;
          total+=read(input);expected+=round*64+i;
          Object.defineProperty(object,'value',{value:object.payload,configurable:true});
          total+=read(input);expected+=round*64+i;
          delete object.value;
          if(read(input)!==round*64+i)return false;
        }
      }
      return collections===32 && total===expected && total===4192256;
    })())JS"},
    {"incremental-GC-property-and-prototype-churn", R"JS((()=>{
      const keep=Array.from({length:8192},(_,index)=>({payload:{index},tag:'keep-'+index}));
      function read(object){return object.value.index;}
      let total=0,expected=0;
      for(let round=0;round<32;round++){
        const prototype={get value(){collectSlice();return this.payload;}};
        collectSlice();
        for(let i=0;i<64;i++){
          const index=(round*64+i)%keep.length,object=keep[index];
          Object.setPrototypeOf(object,prototype);
          object.payload={index:round*64+i};
          total+=read(object);expected+=round*64+i;
          Object.defineProperty(object,'value',{value:object.payload,configurable:true});
          total+=read(object);expected+=round*64+i;
          delete object.value;
        }
      }
      collect();
      return total===expected && total===4192256 && keep[2047].payload.index===2047 && keep[8191].tag==='keep-8191';
    })())JS"},
    {"short-scripted-and-native-call-arguments", R"JS((()=>{
      const root={marker:17};
      function optional(a,b,c,d){
        if(arguments.length===1)collectSlice();
        return [arguments.length,a,b,c,d];
      }
      function unwind(a,b,c){try{if(a===42)throw root;return arguments.length;}finally{collectSlice();}}
      for(let i=0;i<256;i++){
        const zero=optional(),one=optional(root),two=optional(root,7),three=optional(root,7,8);
        if(zero[0]!==0 || zero.slice(1).some(x=>x!==undefined) ||
           one[0]!==1 || one[1]!==root || one[2]!==undefined || one[4]!==undefined ||
           two[0]!==2 || two[2]!==7 || two[3]!==undefined ||
           three[0]!==3 || three[3]!==8 || three[4]!==undefined)return false;
        if(nativeShort()!==0 || nativeShort(7)!==107 || nativeShort(7,9)!==207 ||
           nativeShort(7,9,11,13)!==407 || nativeShort(7,9,11,13,15,17)!==607)return false;
        if(!Number.isNaN(Math.pow()) || !Number.isNaN(Math.pow(2)) || Math.max()!==-Infinity)return false;
        if(unwind()!==0 || unwind(1)!==1)return false;
        try{unwind(42);return false;}catch(error){if(error!==root)return false;}
      }
      return root.marker===17;
    })())JS"},
#ifdef PHASE45_PORTABLE_GUARDS_PROBE
#include "spidermonkey-portable-guards.inc"
#endif
};
int main()
{
    if (!JS_Init()) return 1;
    unsigned checks=0; bool ok=true;
    for (unsigned iteration=0;iteration<3 && ok;++iteration)
    {
        JSContext* cx=JS_NewContext(64*1024*1024);
        if (!cx) {ok=false;break;}
        if (!JS::InitSelfHostedCode(cx)) ok=false;
        if (ok)
        {
            JS::RealmOptions options;
            JS::RootedObject global(cx,JS_NewGlobalObject(cx,&globalClass,nullptr,JS::FireOnNewGlobalHook,options));
            if (!global) ok=false;
            else
            {
                JSAutoRealm realm(cx,global);
                ok=JS::InitRealmStandardClasses(cx) && JS_DefineFunction(cx,global,"collect",collect,0,0) &&
                   JS_DefineFunction(cx,global,"collectSlice",collectSlice,0,0) &&
                   JS_DefineFunction(cx,global,"nativeShort",nativeShort,4,0);
                JS_SetGCParameter(cx,JSGC_INCREMENTAL_GC_ENABLED,true);
                for (const auto& test:cases)
                {
                    if (!ok) break;
                    JS::SourceText<mozilla::Utf8Unit> source;
                    JS::CompileOptions compileOptions(cx);compileOptions.setFileAndLine(test.name,1);
                    JS::RootedValue result(cx);
                    ok=source.init(cx,test.code,std::strlen(test.code),JS::SourceOwnership::Borrowed) &&
                       JS::Evaluate(cx,compileOptions,source,&result) && result.isBoolean() && result.toBoolean();
                    if (ok) {JS_GC(cx);++checks;}
                    else std::fprintf(stderr,"FAILED: %s context %u\n",test.name,iteration);
                }
            }
        }
        JS_DestroyContext(cx);
    }
    JS_ShutDown();
    ok=ok && incrementalYields>0;
    std::printf("{\"passed\":%s,\"checks\":%u,\"incrementalYields\":%u}\n",ok?"true":"false",checks,incrementalYields);
    return ok?0:2;
}
