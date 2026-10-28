/* Copyright (C) 2026 Wildfire Games.
 *
 * Permission is hereby granted, free of charge, to any person obtaining
 * a copy of this software and associated documentation files (the
 * "Software"), to deal in the Software without restriction, including
 * without limitation the rights to use, copy, modify, merge, publish,
 * distribute, sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so, subject to
 * the following conditions:
 *
 * The above copyright notice and this permission notice shall be included
 * in all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
 * EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
 * MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
 * IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
 * CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
 * TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
 * SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 */

/*
 * OS-specific support functions relating to CPU and memory
 */

#include "precompiled.h"

#include "lib/sysdep/os_cpu.h"

#include "lib/alignment.h"
#include "lib/code_annotation.h"
#include "lib/sysdep/os.h"

#if OS_WIN
# include "lib/sysdep/os/win/wcpu.h"
#endif

static const StatusDefinition osCpuStatusDefinitions[] = {
	{ ERR::OS_CPU_RESTRICTED_AFFINITY, L"Cannot set desired CPU affinity" }
};
STATUS_ADD_DEFINITIONS(osCpuStatusDefinitions);


double os_cpu_ClockFrequency()
{
	static double clockFrequency;
	if(clockFrequency != 0.0)	// already initialized
		return clockFrequency;

#if OS_WIN
	std::uint32_t freqMhz;
	if(wcpu_ReadFrequencyFromRegistry(freqMhz) == INFO::OK)
		return clockFrequency = freqMhz * 1e6;
#endif

	return clockFrequency = -1.0;	// unknown
}


size_t os_cpu_MemorySize()
{
	static size_t memorySize;
	if(memorySize != 0)	// already initialized
		return memorySize;

	memorySize = os_cpu_QueryMemorySize();
	return memorySize;
}
