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

#include "precompiled.h"

#include "HttpServer.h"

#include "ps/Future.h"
#include "ps/TaskManager.h"

#include <httplib.h>
#include <queue>

namespace
{
class TaskQueueAdapter : public httplib::TaskQueue
{
public:
	bool enqueue(std::function<void()> fn) override
	{
		// Remove finished
		while (!m_Futures.empty() && m_Futures.front().IsDone())
		{
			m_Futures.front().Get();
			m_Futures.pop();
		}

		m_Futures.push({g_TaskManager, fn});
		return true;
	}

	void shutdown() override
	{
		m_Futures = {};
	}
private:
	std::queue<Future<void>> m_Futures;
};
} // namespace

namespace PS::Net
{
std::unique_ptr<httplib::Server> createHttpServer() {
	auto server = std::make_unique<httplib::Server>();
	server->new_task_queue = [] { return new TaskQueueAdapter(); };
    return server;
}
} // namespace PS::Net
