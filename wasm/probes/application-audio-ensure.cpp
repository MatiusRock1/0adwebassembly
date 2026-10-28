#include "application-audio-ensure.h"
#include <atomic>
#include <iostream>
#include <stdexcept>
#include <thread>

using Queue = WasmApplication::AudioEnsureQueue<int>;
int checks = 0;
void check(bool result)
{
    if (!result)
        throw std::runtime_error("audio ensure check " + std::to_string(checks + 1));
    ++checks;
}

template<typename Predicate> void until(Predicate predicate)
{
    const auto deadline = Queue::Clock::now() + std::chrono::seconds(5);
    while (!predicate())
    {
        if (Queue::Clock::now() >= deadline)
            throw std::runtime_error("audio ensure thread did not progress");
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
}

int main()
{
    Queue queue;
    int music = 1, ambient = 2, unknown = 3;
    check(!queue.Request(&unknown));
    check(queue.Track(&music) && queue.Track(&ambient) && !queue.Track(&music));
    for (int i = 0; i < 20000; ++i)
    {
        queue.Request(&music);
        queue.Request(&ambient);
    }
    auto batch = queue.WaitUntil(Queue::Clock::now());
    check(batch.size() == 2 && batch[0].item == &music && batch[1].item == &ambient);
    check(queue.WaitUntil(Queue::Clock::now()).empty());
    queue.Request(&music);
    queue.Forget(&music);
    check(!queue.IsCurrent(batch[0]) && queue.WaitUntil(Queue::Clock::now()).empty());
    // Re-register exactly the same address; an extracted old ticket stays invalid.
    queue.Track(&music);
    queue.Request(&music);
    auto recycled = queue.WaitUntil(Queue::Clock::now());
    check(recycled.size() == 1 && recycled[0].generation != batch[0].generation &&
        queue.IsCurrent(recycled[0]) && !queue.IsCurrent(batch[0]));

    const auto caller = std::this_thread::get_id();
    std::atomic<bool> entered{false}, release{false}, executedOffThread{false};
    queue.Request(&music);
    std::thread worker([&] {
        auto ready = queue.WaitUntil(Queue::Clock::now() + std::chrono::seconds(5));
        if (ready.size() == 1 && queue.IsCurrent(ready[0]))
        {
            executedOffThread = std::this_thread::get_id() != caller;
            entered = true;
            until([&] { return release.load(); }); // a stalled backend query
        }
    });
    until([&] { return entered.load(); });
    // The game can continue posting while the audio worker waits on its backend.
    bool posted = true;
    for (int i = 0; i < 20000; ++i)
        posted = queue.Request(&ambient) && posted;
    release = true;
    worker.join();
    check(posted && executedOffThread);
    auto pending = queue.WaitUntil(Queue::Clock::now());
    check(pending.size() == 1 && pending[0].item == &ambient);

    const auto deadline = Queue::Clock::now() + std::chrono::milliseconds(20);
    check(queue.WaitUntil(deadline).empty() && Queue::Clock::now() >= deadline);
    std::atomic<bool> waiting{false}, woke{false};
    std::thread sleeper([&] {
        waiting = true;
        queue.WaitUntil(Queue::Clock::now() + std::chrono::seconds(30));
        woke = true;
    });
    until([&] { return waiting.load(); });
    queue.Close();
    until([&] { return woke.load(); });
    sleeper.join();
    check(!queue.IsCurrent(recycled[0]) && !queue.Request(&music) && !queue.Track(&unknown));
    std::cout << "{\"passed\":true,\"checks\":" << checks << "}\n";
}
