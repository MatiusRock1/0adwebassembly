/* Copyright (C) 2025 Wildfire Games.
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
 * various utility functions.
 */

#include "precompiled.h"

#include "lib.h"

#include "lib/status.h"

//-----------------------------------------------------------------------------
// type conversion

// these avoid a common mistake in using >> (ANSI requires shift count be
// less than the bit width of the type).

std::uint32_t u64_hi(std::uint64_t x)
{
	return static_cast<std::uint32_t>(x >> 32);
}

std::uint32_t u64_lo(std::uint64_t x)
{
	return static_cast<std::uint32_t>(x & 0xFFFFFFFF);
}

std::uint16_t u32_hi(std::uint32_t x)
{
	return static_cast<std::uint16_t>(x >> 16);
}

std::uint16_t u32_lo(std::uint32_t x)
{
	return static_cast<std::uint16_t>(x & 0xFFFF);
}


std::uint64_t u64_from_u32(std::uint32_t hi, std::uint32_t lo)
{
	std::uint64_t x = static_cast<std::uint64_t>(hi);
	x <<= 32;
	x |= lo;
	return x;
}

std::uint32_t u32_from_u16(std::uint16_t hi, std::uint16_t lo)
{
	std::uint32_t x = static_cast<std::uint32_t>(hi);
	x <<= 16;
	x |= lo;
	return x;
}


// input in [0, 1); convert to std::uint8_t range
std::uint8_t u8_from_double(double in)
{
	if(!(0.0 <= in && in < 1.0))
	{
		DEBUG_WARN_ERR(ERR::LOGIC);	// clampf not in [0,1)
		return 255;
	}

	int l = (int)(in * 255.0);
	ENSURE((unsigned)l <= 255u);
	return static_cast<std::uint8_t>(l);
}

// input in [0, 1); convert to std::uint16_t range
std::uint16_t u16_from_double(double in)
{
	if(!(0.0 <= in && in < 1.0))
	{
		DEBUG_WARN_ERR(ERR::LOGIC);	// clampf not in [0,1)
		return 65535;
	}

	long l = (long)(in * 65535.0);
	ENSURE((unsigned long)l <= 65535u);
	return static_cast<std::uint16_t>(l);
}
