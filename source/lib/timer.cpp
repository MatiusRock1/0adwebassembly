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
 * platform-independent high resolution timer
 */

#include "precompiled.h"

#include "timer.h"

#include "lib/module_init.h"
#include "lib/posix/posix_types.h"
#include "lib/status.h"
#include "lib/sysdep/os.h"
#include "lib/utf8.h"

#include <algorithm>
#include <ctime>
#include <mutex>
#include <sstream>

#if OS_WIN
#include "lib/sysdep/os/win/win.h"
#endif
#if OS_UNIX
# include <unistd.h>
# include <time.h>
#endif

#if OS_UNIX || OS_WIN
# define HAVE_GETTIMEOFDAY 1
#else
# define HAVE_GETTIMEOFDAY 0
#endif

#if (defined(_POSIX_TIMERS) && _POSIX_TIMERS > 0) || OS_MACOSX
# define HAVE_CLOCK_GETTIME 1
#else
# define HAVE_CLOCK_GETTIME 0
#endif

// rationale for wrapping gettimeofday and clock_gettime, instead of just
// emulating them where not available: allows returning higher-resolution
// timer values than their us / ns interface, via double [seconds].
// they're also not guaranteed to be monotonic.

#if OS_WIN
static LARGE_INTEGER start;
#elif HAVE_CLOCK_GETTIME
static struct timespec start;
#elif HAVE_GETTIMEOFDAY
static struct timeval start;
#endif


//-----------------------------------------------------------------------------
// timer API


// Cached because the default implementation may take several milliseconds.
static double resolution;
static Status InitResolution()
{
#if OS_WIN
	LARGE_INTEGER frequency;
	ENSURE(QueryPerformanceFrequency(&frequency));
	resolution = 1.0 / static_cast<double>(frequency.QuadPart);
#elif HAVE_CLOCK_GETTIME
	struct timespec ts;
	if (clock_getres(CLOCK_MONOTONIC, &ts) == 0)
		resolution = ts.tv_nsec * 1e-9;
	else
		resolution = 1e-9;
#elif HAVE_GETTIMEOFDAY
	resolution = 1e-6;
#else
	const double t0 = timer_Time();
	double t1, t2;
	do t1 = timer_Time(); while (t1 == t0);
	do t2 = timer_Time(); while (t2 == t1);
	resolution = t2 - t1;
#endif
	return INFO::OK;
}

void timer_Init()
{
#if OS_WIN
	ENSURE(QueryPerformanceCounter(&start));
#elif HAVE_CLOCK_GETTIME
	ENSURE(clock_gettime(CLOCK_MONOTONIC, &start) == 0);
#elif HAVE_GETTIMEOFDAY
	ENSURE(gettimeofday(&start, 0) == 0);
#endif

	static ModuleInitState initState{ 0 };
	ModuleInit(&initState, InitResolution);
	ENSURE(resolution != 0.0);
}

static std::mutex ensure_monotonic_mutex;
// NB: does not guarantee strict monotonicity - callers must avoid
// dividing by the difference of two equal times.
static void EnsureMonotonic(double& newTime)
{
	std::lock_guard<std::mutex> lock(ensure_monotonic_mutex);
	static double maxTime;
	maxTime = std::max(maxTime, newTime);
	newTime = maxTime;
}

double timer_Time()
{
	double t;

#if OS_WIN
	ENSURE(start.QuadPart); // must have called timer_LatchStartTime first
	LARGE_INTEGER now;
	ENSURE(QueryPerformanceCounter(&now));
	t = static_cast<double>(now.QuadPart - start.QuadPart) * resolution;
#elif HAVE_CLOCK_GETTIME
	ENSURE(start.tv_sec || start.tv_nsec);	// must have called timer_LatchStartTime first
	struct timespec cur;
	ENSURE(clock_gettime(CLOCK_MONOTONIC, &cur) == 0);
	t = (cur.tv_sec - start.tv_sec) + (cur.tv_nsec - start.tv_nsec) * 1e-9;
#elif HAVE_GETTIMEOFDAY
	ENSURE(start.tv_sec || start.tv_usec);	// must have called timer_LatchStartTime first
	struct timeval cur;
	ENSURE(gettimeofday(&cur, 0) == 0);
	t = (cur.tv_sec - start.tv_sec) + (cur.tv_usec - start.tv_usec) * 1e-6;
#else
# error "timer_Time: add timer implementation for this platform!"
#endif

	EnsureMonotonic(t);
	return t;
}


double timer_Resolution()
{
	return resolution;
}
