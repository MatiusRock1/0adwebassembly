/* Copyright (C) 2025 Wildfire Games.
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

#include "ps/Loader.h"

class TestLoader : public CxxTest::TestSuite
{
public:
	void test_PausedYield()
	{
		int position{0};
		PS::Loader::Task task{[](int& p) -> PS::Loader::Task
		{
			p = 1;
			co_yield 50;
			p = 2;
			co_return 0;
		}(position)};

		TS_ASSERT_EQUALS(task.GetProgress(), 0);
		TS_ASSERT(!task.IsDone());
		TS_ASSERT_EQUALS(position, 0);

		task.Step(-1);

		TS_ASSERT_EQUALS(task.GetProgress(), 50);
		TS_ASSERT(!task.IsDone());
		TS_ASSERT_EQUALS(position, 1);

		task.Step(-1);

		TS_ASSERT_EQUALS(task.GetProgress(), 50);
		TS_ASSERT(task.IsDone());
		TS_ASSERT_EQUALS(position, 2);
	}

	void test_UnpausedYield()
	{
		int position{0};
		PS::Loader::Task task{[](int& p) -> PS::Loader::Task
		{
			p = 1;
			co_yield 50;
			p = 2;
			co_return 0;
		}(position)};

		TS_ASSERT_EQUALS(task.GetProgress(), 0);
		TS_ASSERT(!task.IsDone());
		TS_ASSERT_EQUALS(position, 0);

		task.Step(10);

		TS_ASSERT_EQUALS(task.GetProgress(), 50);
		TS_ASSERT(task.IsDone());
		TS_ASSERT_EQUALS(position, 2);
	}

	void test_ForceAwait()
	{
		int position{0};
		PS::Loader::Task task{[](int& p) -> PS::Loader::Task
		{
			p = 1;
			co_yield 50;
			p = 2;
			co_await std::suspend_always{};
			p = 3;
			co_return 0;
		}(position)};

		TS_ASSERT_EQUALS(task.GetProgress(), 0);
		TS_ASSERT(!task.IsDone());
		TS_ASSERT_EQUALS(position, 0);

		task.Step(10);

		TS_ASSERT_EQUALS(task.GetProgress(), 50);
		TS_ASSERT(!task.IsDone());
		TS_ASSERT_EQUALS(position, 2);

		task.Step(-1);

		TS_ASSERT_EQUALS(task.GetProgress(), 50);
		TS_ASSERT(task.IsDone());
		TS_ASSERT_EQUALS(position, 3);
	}
};
