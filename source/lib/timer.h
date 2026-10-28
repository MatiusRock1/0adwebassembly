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

#ifndef INCLUDED_TIMER
#define INCLUDED_TIMER

#include "lib/code_annotation.h"
#include "lib/config2.h"	// CONFIG2_TIMER_ALLOW_RDTSC
#include "lib/debug.h"
#include "lib/sysdep/arch.h"

#include <cstdint>
#include <string>

#if ARCH_X86_X64 && CONFIG2_TIMER_ALLOW_RDTSC
# include "lib/sysdep/os_cpu.h"	// os_cpu_ClockFrequency
# include "lib/sysdep/arch/x86_x64/x86_x64.h"	// x86_x64::rdtsc
#endif

/**
 * timer_Time will subsequently return values relative to the current time.
 **/
void timer_Init();

/**
 * @return high resolution (> 1 us) timestamp [s].
 **/
double timer_Time();

/**
 * @return resolution [s] of the timer.
 **/
double timer_Resolution();

#endif	// #ifndef INCLUDED_TIMER
