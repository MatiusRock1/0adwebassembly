/* Copyright (C) 2026 Wildfire Games. GPL-2.0-or-later. */
#ifndef INCLUDED_BROWSER_SHADER_COMPILE
#define INCLUDED_BROWSER_SHADER_COMPILE
#include <atomic>
#include <emscripten.h>
#include <emscripten/threading.h>

inline bool BrowserParallelShaderCompileAvailable()
{
    return MAIN_THREAD_EM_ASM_INT({
        const gl=GL.currentContext.GLctx;
        if(gl.phase45ParallelCompile===undefined)
            gl.phase45ParallelCompile=gl.getExtension('KHR_parallel_shader_compile');
        return Number(Boolean(gl.phase45ParallelCompile));
    }) != 0;
}

inline bool BrowserWaitForShaderProgram(unsigned program)
{
    alignas(4) std::atomic<int> ready{0};
    MAIN_THREAD_ASYNC_EM_ASM({
        const gl=GL.currentContext.GLctx;
        const extension=gl.phase45ParallelCompile;
        const finish=success=>{Atomics.store(HEAP32,$1>>>2,success?1:2);Atomics.notify(HEAP32,$1>>>2);};
        const poll=()=>{
            try{
                if(!extension || gl.isContextLost() || gl.getProgramParameter(GL.programs[$0],extension.COMPLETION_STATUS_KHR))finish(true);
                else setTimeout(poll,1);
            }catch(error){finish(false);err(error.stack||String(error));}
        };
        poll();
    }, program, &ready);
    while (!ready.load())
    {
        emscripten_current_thread_process_queued_calls();
        emscripten_futex_wait(&ready, 0, 100);
    }
    return ready.load() == 1;
}
#endif
