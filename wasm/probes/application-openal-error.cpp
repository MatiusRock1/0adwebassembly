// CPU-only differential probe using the SDK's real AL functions. Synthetic
// context records avoid opening an audio device; this is not audible-audio QA.
#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <thread>
#include <AL/al.h>
#include <AL/alc.h>
#include <emscripten.h>
#include <emscripten/heap.h>
#include <emscripten/threading.h>

static unsigned checks = 0;
static void Check(bool value, const char* name)
{
    if (!value) { std::fprintf(stderr, "FAILED: %s\n", name); std::abort(); }
    ++checks;
}
static void Current(int id)
{
    if (!alcMakeContextCurrent(reinterpret_cast<ALCcontext*>(id))) std::abort();
}
static void Error(int value)
{
    MAIN_THREAD_EM_ASM({ AL.currentCtx.err = $0; }, value);
}
int main()
{
    Current(0);
    Check(alGetError() == AL_INVALID_OPERATION && alGetError() == AL_INVALID_OPERATION,
          "no context reports invalid operation without clearing it");
    MAIN_THREAD_EM_ASM({
        AL.contexts[1] = ({ id: 1, err: 0 });
        AL.contexts[2] = ({ id: 2, err: 0 });
    });
    Current(1);
    Check(alGetError() == AL_NO_ERROR, "new current context starts clean");
    for (int code : {AL_INVALID_NAME, AL_INVALID_ENUM, AL_INVALID_VALUE, AL_INVALID_OPERATION})
    {
        Error(code);
        Check(alGetError() == code && alGetError() == AL_NO_ERROR,
              "SDK error value and reset-on-read");
    }
    Error(AL_INVALID_NAME);
    Current(2); Error(AL_INVALID_ENUM);
    Current(1);
    const int first = alGetError();
    Current(2);
    Check(first == AL_INVALID_NAME && alGetError() == AL_INVALID_ENUM && alGetError() == 0,
          "inactive contexts retain separate pending errors");
    Error(AL_INVALID_VALUE);
    Current(2);
    Check(alGetError() == AL_INVALID_VALUE && alGetError() == 0,
          "selecting the same context preserves pending error");

    Error(AL_INVALID_NAME);
    std::atomic<unsigned> ready{0}, seen{0}, unexpected{0};
    std::atomic<bool> start{false};
    auto read = [&] {
        ++ready;
        while (!start.load()) std::this_thread::yield();
        for (int i = 0; i < 1000; ++i)
        {
            const int error = alGetError();
            if (error == AL_INVALID_NAME) ++seen;
            else if (error != 0) ++unexpected;
        }
    };
    std::thread a(read), b(read);
    while (ready != 2) std::this_thread::yield();
    start = true; a.join(); b.join();
    Check(seen == 1 && unexpected == 0, "two readers consume one error exactly once");

    Current(1); Error(AL_INVALID_NAME);
    Current(2); Error(AL_INVALID_ENUM);
    std::atomic<bool> stop{false};
    std::atomic<unsigned> names{0}, enums{0}, other{0};
    auto collect = [&](int code) {
        if (code == AL_INVALID_NAME) ++names;
        else if (code == AL_INVALID_ENUM) ++enums;
        else if (code != 0) ++other;
    };
    std::thread reader([&] { while (!stop.load()) collect(alGetError()); });
    for (int i = 0; i < 1000; ++i) { Current(1); Current(1); Current(2); }
    stop = true; reader.join();
    Current(1); collect(alGetError()); Current(2); collect(alGetError());
    Check(names == 1 && enums == 1 && other == 0,
          "context switches and same-context selection race without lost or revived errors");

    const size_t previous = emscripten_get_heap_size();
    Check(emscripten_resize_heap(previous + 65536), "shared heap grows");
    Error(AL_INVALID_OPERATION);
    Check(alGetError() == AL_INVALID_OPERATION && alGetError() == 0,
          "error state survives memory growth");
    Current(0);
    MAIN_THREAD_EM_ASM({
        delete AL.contexts[1];
        AL.contexts[1] = ({ id: 1, err: 0xa003 });
    });
    Current(1);
    Check(alGetError() == AL_INVALID_VALUE && alGetError() == 0,
          "context id reuse does not reuse the destroyed object's error");
    Current(0);
    Check(alGetError() == AL_INVALID_OPERATION, "context removal publishes no context");
    Current(1);
    unsigned checksum = 0;
    double milliseconds[3];
    for (unsigned trial = 0; trial < 3; ++trial)
    {
        const double started = emscripten_get_now();
        for (unsigned i = 0; i < 10000; ++i) checksum |= alGetError();
        milliseconds[trial] = emscripten_get_now() - started;
    }
    Check(checksum == 0, "clean error-query loop checksum");
    std::printf("{\"passed\":true,\"checks\":%u,\"readsPerTrial\":10000,\"milliseconds\":[%.6f,%.6f,%.6f]}\n",
                checks, milliseconds[0], milliseconds[1], milliseconds[2]);
}
