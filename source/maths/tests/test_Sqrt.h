/* Copyright (C) 2026 Wildfire Games.
 * This file is part of 0 A.D.
 *
 * 0 A.D. is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 2 of the License, or
 * (at your option) any later version.
 *
 * 0 A.D. is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with 0 A.D.  If not, see <http://www.gnu.org/licenses/>.
 */

#include "lib/self_test.h"

#include "maths/Sqrt.h"

#include <cmath>
#include <cstddef>
#include <random>

class TestSqrt : public CxxTest::TestSuite
{
public:
	void t(std::uint32_t n)
	{
		TS_ASSERT_EQUALS(isqrt64(static_cast<std::uint64_t>(n) * static_cast<std::uint64_t>(n)), n);
	}

	void s(std::uint64_t n, std::uint64_t exp)
	{
		TS_ASSERT_EQUALS(static_cast<std::uint64_t>(isqrt64(n)), exp);
	}

	void test_sqrt()
	{
		t(0);
		t(1);
		t(2);
		t(255);
		t(256);
		t(257);
		t(65535);
		t(65536);
		t(65537);
		t(16777215);
		t(16777216);
		t(16777217);
		t(2147483647);
		t(2147483648u);
		t(2147483649u);
		t(4294967295u);

		s(2, 1);
		s(3, 1);
		s(4, 2);
		s(255, 15);
		s(256, 16);
		s(257, 16);
		s(65535, 255);
		s(65536, 256);
		s(65537, 256);
		s(999999, 999);
		s(1000000, 1000);
		s(1000001, 1000);
		s(static_cast<std::uint64_t>(-1), 4294967295u);
	}

	void test_random()
	{
		// Test with some random std::uint64_ts, to make sure the output agrees with floor(sqrt(double))
		// (TODO: This might be making non-portable assumptions about sqrt(double))

		std::mt19937 rng;
		std::uniform_int_distribution<std::uint64_t> ints(0, static_cast<std::uint64_t>(-1));

		for (size_t i = 0; i < 1024; ++i)
		{
			std::uint64_t n = ints(rng);
			s(n, static_cast<std::uint64_t>(sqrt(static_cast<double>(n))));
		}
	}
};
