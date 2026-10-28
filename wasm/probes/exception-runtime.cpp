// CPU-only ABI/overhead probe. Never a displayed-frame performance gate.
#include <atomic>
#include <csetjmp>
#include <cstdint>
#include <cstdio>
#include <exception>
#include <stdexcept>
#include <string>
#include <thread>
#include <emscripten.h>
#include <png.h>

extern "C" uint32_t Phase45ForeignValue(uint32_t);
extern "C" void Phase45ForeignCall(void (*)());
static std::atomic<int> active{0};
struct Guard { Guard(){++active;} ~Guard(){--active;} };
static void Throw() { Guard guard;throw std::runtime_error("phase45 expected exception"); }
static void PngError(png_structp png,png_const_charp) { png_longjmp(png,1); }
static bool PngJump()
{
    png_structp png=png_create_read_struct(PNG_LIBPNG_VER_STRING,nullptr,PngError,nullptr);
    if(!png)return false;
    bool jumped=false;
    if(setjmp(png_jmpbuf(png)))jumped=true;
    else png_error(png,"phase45 expected PNG error");
    png_destroy_read_struct(&png,nullptr,nullptr);
    return jumped;
}
static unsigned checks=0;
static void Check(bool value,const char* name)
{ if(!value){std::fprintf(stderr,"FAILED: %s\n",name);std::terminate();}++checks; }

static uint32_t Work(unsigned count)
{
    // Volatile indirect target and observable RAII cleanup keep the normal
    // call/unwind path present. The foreign TU is built without exceptions,
    // as SpiderMonkey is. No exception is thrown in the timed hot loop.
    uint32_t (*volatile callback)(uint32_t)=Phase45ForeignValue;
    uint32_t value=0x45ad45u,stamp=0;
    struct Scope { uint32_t& stamp;unsigned i;~Scope(){stamp=stamp*33u+i;} };
    for(unsigned i=0;i<count;++i){Scope scope{stamp,i};value=callback(value);}
    return value^stamp;
}
static uint32_t Reference(unsigned count)
{
    uint32_t value=0x45ad45u,stamp=0;
    for(unsigned i=0;i<count;++i){value=(value*1664525u+1013904223u)^((value>>7)|(value<<25));stamp=stamp*33u+i;}
    return value^stamp;
}
int main()
{
    bool caught=false;
    try{Guard guard;Throw();}catch(const std::runtime_error& error){caught=std::string(error.what())=="phase45 expected exception";}
    Check(caught && active==0,"local exception and RAII");caught=false;
    try{Guard guard;Phase45ForeignCall(Throw);}catch(const std::exception&){caught=true;}
    Check(caught && active==0,"unwind across no-exceptions foreign TU");caught=false;
    try{try{Throw();}catch(...){throw;}}catch(const std::runtime_error&){caught=true;}
    Check(caught && active==0,"rethrow");
    std::exception_ptr pending;
    std::thread worker([&]{try{Throw();}catch(...){pending=std::current_exception();}});worker.join();
    caught=false;try{std::rethrow_exception(pending);}catch(const std::runtime_error&){caught=true;}
    Check(caught && active==0,"exception_ptr across pthread join");
    Check(PngJump(),"libpng longjmp matches C++ exception mode");
    Work(100000);
    double milliseconds[3];uint32_t checksum=0;
    for(unsigned trial=0;trial<3;++trial){double start=emscripten_get_now();checksum=Work(2000000);milliseconds[trial]=emscripten_get_now()-start;}
    Check(checksum==Reference(2000000),"indirect hot-loop checksum");
    std::printf("{\"passed\":true,\"checks\":%u,\"checksum\":%u,\"callsPerTrial\":2000000,\"milliseconds\":[%.6f,%.6f,%.6f]}\n",checks,checksum,milliseconds[0],milliseconds[1],milliseconds[2]);
}
