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
 * byte order (endianness) support routines.
 */

#include "precompiled.h"

#include "byte_order.h"

#include "lib/bits.h"

#include <algorithm>
#include <cstring>

#ifndef swap16
std::uint16_t swap16(const std::uint16_t x)
{
	return static_cast<std::uint16_t>(((x & 0xff) << 8) | (x >> 8));
}
#endif

#ifndef swap32
std::uint32_t swap32(const std::uint32_t x)
{
	return (x << 24) |
		(x >> 24) |
		((x << 8) & 0x00ff0000) |
		((x >> 8) & 0x0000ff00);
}
#endif

#ifndef swap64
std::uint64_t swap64(const std::uint64_t x)
{
	const std::uint32_t lo = static_cast<std::uint32_t>(x & 0xFFFFFFFF);
	const std::uint32_t hi = static_cast<std::uint32_t>(x >> 32);
	std::uint64_t ret = swap32(lo);
	ret <<= 32;
	// careful: must shift var of type std::uint64_t, not std::uint32_t
	ret |= swap32(hi);
	return ret;
}
#endif


//-----------------------------------------------------------------------------


std::uint16_t read_le16(const void* p)
{
	std::uint16_t n;
	memcpy(&n, p, sizeof(n));
	return to_le16(n);
}

std::uint32_t read_le32(const void* p)
{
	std::uint32_t n;
	memcpy(&n, p, sizeof(n));
	return to_le32(n);
}

std::uint64_t read_le64(const void* p)
{
	std::uint64_t n;
	memcpy(&n, p, sizeof(n));
	return to_le64(n);
}


std::uint16_t read_be16(const void* p)
{
	std::uint16_t n;
	memcpy(&n, p, sizeof(n));
	return to_be16(n);
}

std::uint32_t read_be32(const void* p)
{
	std::uint32_t n;
	memcpy(&n, p, sizeof(n));
	return to_be32(n);
}

std::uint64_t read_be64(const void* p)
{
	std::uint64_t n;
	memcpy(&n, p, sizeof(n));
	return to_be64(n);
}


void write_le16(void* p, std::uint16_t x)
{
	std::uint16_t n = to_le16(x);
	memcpy(p, &n, sizeof(n));
}

void write_le32(void* p, std::uint32_t x)
{
	std::uint32_t n = to_le32(x);
	memcpy(p, &n, sizeof(n));
}

void write_le64(void* p, std::uint64_t x)
{
	std::uint64_t n = to_le64(x);
	memcpy(p, &n, sizeof(n));
}


void write_be16(void* p, std::uint16_t x)
{
	std::uint16_t n = to_be16(x);
	memcpy(p, &n, sizeof(n));
}

void write_be32(void* p, std::uint32_t x)
{
	std::uint32_t n = to_be32(x);
	memcpy(p, &n, sizeof(n));
}

void write_be64(void* p, std::uint64_t x)
{
	std::uint64_t n = to_be64(x);
	memcpy(p, &n, sizeof(n));
}


std::uint64_t movzx_le64(const std::uint8_t* p, size_t size_bytes)
{
	std::uint64_t number = 0;
	for(size_t i = 0; i < std::min(size_bytes, (size_t)8u); i++)
		number |= static_cast<std::uint64_t>(p[i]) << (i*8);

	return number;
}

std::uint64_t movzx_be64(const std::uint8_t* p, size_t size_bytes)
{
	std::uint64_t number = 0;
	for(size_t i = 0; i < std::min(size_bytes, (size_t)8u); i++)
	{
		number <<= 8;
		number |= p[i];
	}

	return number;
}


static inline std::int64_t SignExtend(std::uint64_t bits, size_t size_bytes)
{
	// no point in sign-extending if >= 8 bytes were requested
	if(size_bytes < 8)
	{
		const std::uint64_t sign_bit = Bit<std::uint64_t>((size_bytes*8)-1);

		// number would be negative in the smaller type,
		// so sign-extend, i.e. set all more significant bits.
		if(bits & sign_bit)
		{
			const std::uint64_t valid_bit_mask = (sign_bit+sign_bit)-1;
			bits |= ~valid_bit_mask;
		}
	}

	const std::int64_t number = static_cast<std::int64_t>(bits);
	return number;
}

std::int64_t movsx_le64(const std::uint8_t* p, size_t size_bytes)
{
	const std::uint64_t number = movzx_le64(p, size_bytes);
	return SignExtend(number, size_bytes);
}

std::int64_t movsx_be64(const std::uint8_t* p, size_t size_bytes)
{
	const std::uint64_t number = movzx_be64(p, size_bytes);
	return SignExtend(number, size_bytes);
}
