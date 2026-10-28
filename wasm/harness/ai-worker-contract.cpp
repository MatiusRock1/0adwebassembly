#include "simulation2/helpers/AIWorkerMailbox.h"
#include "simulation2/helpers/DeferredCommands.h"
#include <cassert>
#include <atomic>
#include <iostream>
#include <string>

struct Worker
{
    std::thread::id owner = std::this_thread::get_id();
    int rng = 7;
    ~Worker() { assert(owner == std::this_thread::get_id()); }
    int Next() { assert(owner == std::this_thread::get_id()); return rng = (rng * 17 + 3) % 101; }
};

int main()
{
    const auto main = std::this_thread::get_id();
    std::atomic<int> finished{0};
    {
        AIWorkerMailbox<Worker> mailbox([main] {
            assert(std::this_thread::get_id() != main); return std::make_unique<Worker>();
        }, [&] { assert(std::this_thread::get_id() != main); ++finished; });
        Worker reference;
        for (int turn = 0; turn < 200; ++turn)
        {
            std::vector<int> input{turn};
            const auto result = mailbox.Submit([input](Worker& worker) {
                for (int i=0; i<input[0]%13; ++i) std::this_thread::yield();
                return std::vector<int>{input[0], worker.Next()};
            }).share();
            input[0] = -1;
            DeferredCommands<int> pending;
            std::vector<int> commands{11};
            pending.Reserve(commands.size(), [result] { return result.get(); });
            commands.push_back(22); // Commands queued after AI must stay after it.
            pending.Reserve(commands.size(), [] { return std::vector<int>{33}; });
            pending.Reserve(commands.size(), [] { return std::vector<int>{44}; });
            pending.Resolve(commands);
            assert((commands == std::vector<int>{11,turn,reference.Next(),22,33,44}));
            auto saved = commands; pending.Resolve(commands); assert(commands == saved);
        }
        auto failed = mailbox.Submit([](Worker&) -> int { throw std::runtime_error("AI error"); });
        bool caught = false;
        try { failed.get(); } catch (const std::runtime_error&) { caught = true; }
        assert(caught);
        assert(mailbox.Submit([](Worker&) { return 123; }).get() == 123);
        // Accepted work drains before destruction, without polling or sleeps.
        mailbox.Submit([&](Worker&) { ++finished; });
    }
    assert(finished == 2);
    bool startupFailed = false;
    try {
        AIWorkerMailbox<Worker> mailbox([]() -> std::unique_ptr<Worker> { throw std::runtime_error("startup"); }, [&] { ++finished; });
    } catch (const std::runtime_error&) { startupFailed = true; }
    assert(startupFailed && finished == 3);
    {
        DeferredCommands<int> pending;
        std::vector<int> commands{1,2};
        pending.Reserve(1, []() -> std::vector<int> { throw std::runtime_error("result"); });
        try { pending.Resolve(commands); assert(false); } catch (const std::runtime_error&) {}
        assert((commands == std::vector<int>{1,2}));
    }
    std::cout << "AI_CONTRACT_PASSED: ownership, owned inputs, 200 ordered turns/RNG, repeated materialization, errors, drain, startup failure\n";
}
