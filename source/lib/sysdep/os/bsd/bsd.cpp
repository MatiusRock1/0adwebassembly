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

#include "precompiled.h"

#include "lib/sysdep/sysdep.h"

#include <climits>

#if defined(__FreeBSD__)
#include <sys/param.h>
#include <sys/sysctl.h>
#else
#include <stdlib.h>
#endif

/**
 * Get the path to the executable
 *
 * In FreeBSD the procfs isn't available by default so use a system call instead.
 */
OsPath sys_ExecutablePathname()
{
	char pathBuffer[PATH_MAX];

#if defined(__FreeBSD__)
	int mib[] = { CTL_KERN, KERN_PROC, KERN_PROC_PATHNAME, -1 };
	size_t length = sizeof(pathBuffer);
	int error = sysctl(mib, 4, pathBuffer, &length, nullptr, 0);
	if (error < 0 || length <= 1)
		return {};
#else
	if (realpath("/proc/curproc/file", pathBuffer) == nullptr)
		return {};
#endif

	return pathBuffer;
}
