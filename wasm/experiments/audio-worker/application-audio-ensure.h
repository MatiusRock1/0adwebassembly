// Isolated experiment: periodic checks only. Actual play/pause/stop retain their
// original ordering. The sound worker owns item execution and removal.
#ifndef INCLUDED_WASM_APPLICATION_AUDIO_ENSURE
#define INCLUDED_WASM_APPLICATION_AUDIO_ENSURE

#include <algorithm>
#include <chrono>
#include <condition_variable>
#include <cstdint>
#include <mutex>
#include <unordered_map>
#include <vector>

namespace WasmApplication
{
template<typename Item>
class AudioEnsureQueue
{
public:
    using Clock = std::chrono::steady_clock;
    struct Ticket
    {
        Item* item;
        uint64_t generation;
    };

    // Called while the sound worker's item-ownership mutex is held.
    bool Track(Item* item)
    {
        std::lock_guard<std::mutex> lock(m_Mutex);
        if (m_Closed || m_Live.count(item))
            return false;
        m_Live.emplace(item, ++m_Generation);
        return true;
    }

    // Called before transferring an item to the list that the game may delete.
    void Forget(Item* item)
    {
        std::lock_guard<std::mutex> lock(m_Mutex);
        m_Live.erase(item);
        m_Pending.erase(std::remove_if(m_Pending.begin(), m_Pending.end(),
            [item](const Ticket& ticket) { return ticket.item == item; }), m_Pending.end());
    }

    bool Request(Item* item)
    {
        {
            std::lock_guard<std::mutex> lock(m_Mutex);
            const auto found = m_Live.find(item);
            if (m_Closed || found == m_Live.end())
                return false;
            // At most one pending check per registered item. Never wait for
            // OpenAL or acquire the worker's item-ownership mutex here.
            if (std::none_of(m_Pending.begin(), m_Pending.end(),
                [item](const Ticket& ticket) { return ticket.item == item; }))
                m_Pending.push_back({item, found->second});
        }
        m_Wake.notify_one();
        return true;
    }

    std::vector<Ticket> WaitUntil(Clock::time_point deadline)
    {
        std::unique_lock<std::mutex> lock(m_Mutex);
        m_Wake.wait_until(lock, deadline, [this] { return m_Closed || !m_Pending.empty(); });
        std::vector<Ticket> ready;
        ready.swap(m_Pending);
        return ready;
    }

    // Caller holds the worker ownership mutex through validation and use.
    // A recycled address never makes a previously extracted ticket valid.
    bool IsCurrent(const Ticket& ticket)
    {
        std::lock_guard<std::mutex> lock(m_Mutex);
        const auto found = m_Live.find(ticket.item);
        return !m_Closed && found != m_Live.end() && found->second == ticket.generation;
    }

    void Close()
    {
        {
            std::lock_guard<std::mutex> lock(m_Mutex);
            m_Closed = true;
            m_Live.clear();
            m_Pending.clear();
        }
        m_Wake.notify_all();
    }

private:
    std::mutex m_Mutex;
    std::condition_variable m_Wake;
    std::unordered_map<Item*, uint64_t> m_Live;
    std::vector<Ticket> m_Pending;
    uint64_t m_Generation = 0;
    bool m_Closed = false;
};
}
#endif
