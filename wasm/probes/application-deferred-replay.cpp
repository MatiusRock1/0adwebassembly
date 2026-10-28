#include "application-deferred-replay.h"
#include <functional>
#include <iostream>
#include <memory>
#include <sstream>
#include <stdexcept>

using WasmApplication::DeferredReplayFlushes;
struct Sink : std::stringbuf
{
    std::string written;
    unsigned flushes = 0;
    bool fail = false;
    std::function<void()> callback;
    int sync() override
    {
        ++flushes;
        if (fail) return -1;
        written += str(); str("");
        if (callback) callback();
        return 0;
    }
};
void Check(bool ok) { if (!ok) throw std::runtime_error("Deferred replay probe failed"); }
int main()
{
    unsigned checks = 0;
    DeferredReplayFlushes queue;
    Sink sink; std::ostream stream(&sink);
    stream << "start {}\n"; queue.Schedule(stream);
    Check(sink.written == "start {}\n" && sink.flushes == 1 && !queue.PendingCount()); ++checks;

    queue.enabled = true;
    const std::string first = "turn 1 200\ncmd 1 {\"type\":\"walk\"}\nend\n";
    stream << first; queue.Schedule(stream);
    Check(queue.PendingCount() == 1 && sink.flushes == 1); ++checks;
    stream << "hash-quick abc\nturn 2 200\nend\n"; queue.Schedule(stream);
    queue.Drain(); queue.Drain();
    Check(sink.written == "start {}\n" + first + "hash-quick abc\nturn 2 200\nend\n" && sink.flushes == 3 && !queue.PendingCount()); ++checks;

    Sink other; std::ostream otherStream(&other);
    auto retiring = std::make_unique<std::ostream>(&sink);
    *retiring << "turn 3 200\nend\n"; queue.Schedule(*retiring); queue.Schedule(*retiring);
    otherStream << "separate replay"; queue.Schedule(otherStream);
    queue.DrainStream(*retiring); retiring.reset();
    Check(queue.PendingCount() == 1 && sink.flushes == 5 && other.flushes == 0);
    queue.Drain(); Check(other.written == "separate replay" && !queue.PendingCount()); ++checks;

    Sink bad; bad.fail = true; std::ostream badStream(&bad);
    queue.Schedule(badStream); queue.Schedule(otherStream); queue.Drain();
    Check(badStream.bad() && bad.flushes == 1 && other.flushes == 2 && !queue.PendingCount()); ++checks;

    bool reentered = false;
    other.callback = [&] { if (!std::exchange(reentered, true)) queue.Schedule(otherStream); };
    queue.Schedule(otherStream); queue.Drain();
    Check(queue.PendingCount() == 1 && other.flushes == 3);
    queue.Drain(); Check(!queue.PendingCount() && other.flushes == 4); other.callback = {}; ++checks;

    for (unsigned i = 0; i < 65; ++i) { otherStream << i << '\n'; queue.Schedule(otherStream); }
    Check(queue.PendingCount() == 1 && other.flushes == 68);
    queue.Drain(); Check(!queue.PendingCount() && other.flushes == 69); ++checks;

    queue.enabled = false; stream << "last\n"; queue.Schedule(stream); queue.DrainStream(stream);
    Check(!queue.PendingCount() && sink.flushes == 6 && sink.written.ends_with("last\n")); ++checks;
    std::cout << "{\"passed\":true,\"checks\":" << checks << "}\n";
}
