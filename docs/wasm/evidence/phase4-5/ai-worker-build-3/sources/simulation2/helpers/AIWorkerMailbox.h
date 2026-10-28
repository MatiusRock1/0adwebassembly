/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef INCLUDED_AIWORKERMAILBOX
#define INCLUDED_AIWORKERMAILBOX
#include <condition_variable>
#include <deque>
#include <functional>
#include <future>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <thread>
#include <type_traits>
#include <utility>

// One permanent owner thread and two bounded slots, including running work.
// Messages own their payloads; no JS handles or borrowed sim pointers may cross.
template<class Worker>
class AIWorkerMailbox
{
public:
    AIWorkerMailbox(std::function<std::unique_ptr<Worker>()> create,
        std::function<void()> finish) : m_Thread([this, create, finish]()
    {
        std::unique_ptr<Worker> worker;
        try { worker = create(); m_Started.set_value(); }
        catch (...) { m_Started.set_exception(std::current_exception()); finish(); return; }
        for (;;)
        {
            std::function<void(Worker&)> task;
            {
                std::unique_lock lock(m_Mutex);
                m_Changed.wait(lock, [this] { return m_Stopping || !m_Tasks.empty(); });
                if (m_Tasks.empty() && m_Stopping) break;
                task = std::move(m_Tasks.front()); m_Tasks.pop_front();
            }
            task(*worker);
            { std::lock_guard lock(m_Mutex); --m_Outstanding; }
            m_Changed.notify_all();
        }
        worker.reset(); // Rooted values and interfaces die on their owner thread.
        finish();
    })
    {
        try { m_Started.get_future().get(); }
        catch (...) { m_Thread.join(); throw; }
    }
    ~AIWorkerMailbox()
    {
        { std::lock_guard lock(m_Mutex); m_Stopping = true; }
        m_Changed.notify_all(); m_Thread.join();
    }
    template<class F>
    auto Submit(F function)
    {
        using Result = std::invoke_result_t<F, Worker&>;
        auto task = std::make_shared<std::packaged_task<Result(Worker&)>>(std::move(function));
        auto future = task->get_future();
        {
            std::unique_lock lock(m_Mutex);
            m_Changed.wait(lock, [this] { return m_Stopping || m_Outstanding < 2; });
            if (m_Stopping) throw std::runtime_error("AI mailbox stopped");
            m_Tasks.emplace_back([task](Worker& worker) { (*task)(worker); });
            ++m_Outstanding;
        }
        m_Changed.notify_all(); return future;
    }
private:
    std::mutex m_Mutex;
    std::condition_variable m_Changed;
    std::deque<std::function<void(Worker&)>> m_Tasks;
    size_t m_Outstanding = 0;
    bool m_Stopping = false;
    std::promise<void> m_Started;
    std::thread m_Thread;
};
#endif
