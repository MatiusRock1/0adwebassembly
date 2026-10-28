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
 * bit-twiddling.
 */

#ifndef INCLUDED_BITS
#define INCLUDED_BITS

#include "lib/code_annotation.h"
#include "lib/debug.h"
#include "lib/status.h"

#include <bit>
#include <climits>
#include <cstddef>
#include <limits>
#include <type_traits>

/**
 * value of bit number \<n\>.
 *
 * @param n bit index.
 *
 * requirements:
 * - T should be an unsigned type
 * - n must be in [0, CHAR_BIT*sizeof(T)), else the result is undefined!
 **/
template<typename T>
inline T Bit(size_t n)
{
	const T one = T(1);
	return (T)(one << n);
}

/**
 * pretty much the same as Bit\<unsigned\>.
 * this is intended for the initialization of enum values, where a
 * compile-time constant is required.
 **/
#define BIT(n) (1u << (n))

template<typename T>
inline bool IsBitSet(T value, size_t index)
{
	const T bit = Bit<T>(index);
	return (value & bit) != 0;
}


// these are declared in the header and inlined to aid compiler optimizations
// (they can easily end up being time-critical).
// note: GCC can't inline extern functions, while VC's "Whole Program
// Optimization" can.

/**
 * a mask that includes the lowest N bits
 *
 * @param numBits Number of bits in mask.
 **/
template<typename T>
inline T bit_mask(size_t numBits)
{
	const T bitsInT = sizeof(T)*CHAR_BIT;
	const T allBits = (T)~T(0);
	// (shifts of at least bitsInT are undefined)
	if(numBits >= bitsInT)
		return allBits;
	// (note: the previous allBits >> (bitsInT-numBits) is not safe
	// because right-shifts of negative numbers are undefined.)
	const T mask = (T)((T(1) << numBits)-1);
	return mask;
}


/**
 * extract the value of bits hi_idx:lo_idx within num
 *
 * example: bits(0x69, 2, 5) == 0x0A
 *
 * @param num number whose bits are to be extracted
 * @param lo_idx bit index of lowest  bit to include
 * @param hi_idx bit index of highest bit to include
 * @return value of extracted bits.
 **/
template<typename T>
inline T bits(T num, size_t lo_idx, size_t hi_idx)
{
	const size_t numBits = (hi_idx - lo_idx)+1;	// # bits to return
	T result = T(num >> lo_idx);
	result = T(result & bit_mask<T>(numBits));
	return result;
}

/**
 * round number up/down to the next given multiple.
 *
 * @param n Number to round.
 * @param multiple Must be a power of two.
 **/
template<typename T>
inline T round_up(T n, T multiple)
{
	ASSERT(multiple > 0);
	ASSERT(std::has_single_bit(static_cast<std::make_unsigned_t<T>>(multiple)));
	const T result = (n + multiple-1) & ~(multiple-1);
	ASSERT(n <= result && result < n+multiple);
	return result;
}

template<typename T>
inline T round_down(T n, T multiple)
{
	ASSERT(multiple > 0);
	ASSERT(std::has_single_bit(static_cast<std::make_unsigned_t<T>>(multiple)));
	const T result = n & ~(multiple-1);
	ASSERT(result <= n && n < result+multiple);
	return result;
}

// evaluates to an expression suitable as an initializer
// for constant static data members.
#define ROUND_UP(n, multiple) (((n) + (multiple)-1) & ~((multiple)-1))

#endif	// #ifndef INCLUDED_BITS
