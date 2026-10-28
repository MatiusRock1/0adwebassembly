cmake_minimum_required(VERSION 3.20)
project(0ad_wasm_probes LANGUAGES CXX)

# Toolchain probe only: this target does not contain Pyrogenesis.
add_executable(emscripten-smoke probes/smoke.cpp)
target_compile_features(emscripten-smoke PRIVATE cxx_std_17)
if(EMSCRIPTEN)
    file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/package.json" "{\"type\":\"commonjs\"}\n")
    set_target_properties(emscripten-smoke PROPERTIES SUFFIX ".js")
    target_link_options(emscripten-smoke PRIVATE "-sENVIRONMENT=web,node" "-sASSERTIONS=1")
endif()

# Optional authentic engine fixture. Source root is the pinned checkout with
# the documented platform and component-selection patches applied.
set(HEADLESS_SOURCE_ROOT "" CACHE PATH "Prepared 0 A.D. source directory")
set(SPIDERMONKEY_INCLUDE_DIR "" CACHE PATH "SpiderMonkey 128 headers")
set(SPIDERMONKEY_LIBRARY "" CACHE FILEPATH "SpiderMonkey engine library")
set(HEADLESS_DEPENDENCY_INCLUDE_DIR "" CACHE PATH "Portable Boost/fmt/XML headers")
set(SPIDERMONKEY_WASM_OBJECT_ROOT "" CACHE PATH "SpiderMonkey WASM object directory")
set(HEADLESS_TEST_SCRIPT "" CACHE FILEPATH "Original upstream component test.js")
option(HEADLESS_BROWSER "Build the authentic fixture for browser pthreads" OFF)
if(HEADLESS_SOURCE_ROOT)
    set(engine_sources
        scriptinterface/Context.cpp scriptinterface/Interface.cpp
        scriptinterface/Conversions.cpp scriptinterface/Exceptions.cpp
        scriptinterface/JSON.cpp scriptinterface/ModuleLoader.cpp
        scriptinterface/Promises.cpp scriptinterface/Stats.cpp
        scriptinterface/StructuredClone.cpp ps/CStr.cpp ps/Errors.cpp
        ps/Filesystem.cpp lib/utf8.cpp lib/secure_crt.cpp lib/status.cpp
        lib/sysdep/rtl/gcc/gcc.cpp lib/file/vfs/vfs_util.cpp lib/regex.cpp
        simulation2/system/ComponentManager.cpp simulation2/system/SimContext.cpp
        simulation2/system/IComponent.cpp simulation2/system/CmpPtr.cpp simulation2/system/DynamicSubscription.cpp
        simulation2/system/ParamNode.cpp simulation2/scripting/ScriptComponent.cpp
        simulation2/scripting/MessageTypeConversions.cpp
        simulation2/scripting/EngineScriptConversions.cpp
        simulation2/serialization/ISerializer.cpp
        simulation2/components/CCmpTest.cpp simulation2/components/ICmpTest.cpp)
    list(TRANSFORM engine_sources PREPEND "${HEADLESS_SOURCE_ROOT}/")
    if(EMSCRIPTEN)
        if(HEADLESS_BROWSER)
            set(headless_target pyrogenesis-browser)
        else()
            set(headless_target pyrogenesis-wasm)
        endif()
    else()
        set(headless_target pyrogenesis-headless)
    endif()
    # secure_crt.cpp implements narrow/wide versions from the same source.
    add_library(headless-wide-crt OBJECT "${HEADLESS_SOURCE_ROOT}/lib/secure_crt.cpp")
    add_executable(${headless_target} harness/simulation.cpp harness/simulation-update.cpp harness/platform.cpp
        ${engine_sources} $<TARGET_OBJECTS:headless-wide-crt>)
    foreach(target ${headless_target} headless-wide-crt)
        target_compile_features(${target} PRIVATE cxx_std_20)
        target_compile_definitions(${target} PRIVATE FMT_HEADER_ONLY NDEBUG
            CONFIG_ENABLE_PCH=0 CONFIG2_AUDIO=0 CONFIG2_NVTT=0 CONFIG2_LOBBY=0)
        target_include_directories(${target} PRIVATE harness/adapters
            "${HEADLESS_SOURCE_ROOT}" "${HEADLESS_SOURCE_ROOT}/pch/scriptinterface"
            "${HEADLESS_DEPENDENCY_INCLUDE_DIR}" "${SPIDERMONKEY_INCLUDE_DIR}")
        target_compile_options(${target} PRIVATE -pthread -ffunction-sections -fdata-sections)
    endforeach()
    target_compile_definitions(headless-wide-crt PRIVATE WSECURE_CRT)
    target_link_libraries(${headless_target} PRIVATE "${SPIDERMONKEY_LIBRARY}")
    target_link_options(${headless_target} PRIVATE -pthread -Wl,--gc-sections)
    if(EMSCRIPTEN)
        file(GLOB_RECURSE sm_support
            "${SPIDERMONKEY_WASM_OBJECT_ROOT}/mfbt/*.o"
            "${SPIDERMONKEY_WASM_OBJECT_ROOT}/mozglue/*.o"
            "${SPIDERMONKEY_WASM_OBJECT_ROOT}/memory/*.o")
        target_link_libraries(${headless_target} PRIVATE
            "${SPIDERMONKEY_WASM_OBJECT_ROOT}/wasm32-unknown-emscripten/release/libjsrust.a"
            "${SPIDERMONKEY_WASM_OBJECT_ROOT}/build/pure_virtual/libpure_virtual.a" ${sm_support})
        target_compile_options(${headless_target} PRIVATE -fexceptions)
        target_link_options(${headless_target} PRIVATE -fexceptions --use-port=zlib
            -sALLOW_MEMORY_GROWTH=1 -sSTACK_SIZE=5242880 -sASSERTIONS=2
            "--embed-file" "${HEADLESS_TEST_SCRIPT}@/scenario/test.js")
        if(HEADLESS_BROWSER)
            target_sources(${headless_target} PRIVATE harness/browser-main.cpp)
            target_compile_definitions(${headless_target} PRIVATE WASM_BROWSER_FIXTURE)
            target_link_options(${headless_target} PRIVATE
                -sENVIRONMENT=web,worker -sMODULARIZE=1 -sEXPORT_ES6=1
                -sEXPORT_NAME=createPyrogenesis -sPROXY_TO_PTHREAD=1
                -sPTHREAD_POOL_SIZE=2 -sEXIT_RUNTIME=1)
            set_target_properties(${headless_target} PROPERTIES SUFFIX ".mjs")
        else()
            set_target_properties(${headless_target} PROPERTIES SUFFIX ".js")
        endif()
    endif()
endif()
