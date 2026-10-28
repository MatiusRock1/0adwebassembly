/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef INCLUDED_DEFERREDCOMMANDS
#define INCLUDED_DEFERREDCOMMANDS
#include <functional>
#include <iterator>
#include <utility>
#include <vector>

// Reserve at publication, not completion. Producers run on the sim thread.
template<class Command>
class DeferredCommands
{
public:
    void Reserve(size_t offset, std::function<std::vector<Command>()> producer)
    { m_Batches.emplace_back(offset, std::move(producer)); }
    void Resolve(std::vector<Command>& commands)
    {
        if (m_Batches.empty()) return;
        // Resolve before moving any rooted commands. Failure leaves the queue
        // intact; producers must be repeatable reads of immutable results.
        std::vector<std::vector<Command>> batches;
        for (auto& [offset, producer] : m_Batches) batches.push_back(producer());
        std::vector<Command> result;
        size_t batch = 0;
        for (size_t i = 0; i <= commands.size(); ++i)
        {
            while (batch < m_Batches.size() && m_Batches[batch].first == i)
            {
                auto& values = batches[batch++];
                result.insert(result.end(), std::make_move_iterator(values.begin()), std::make_move_iterator(values.end()));
            }
            if (i < commands.size()) result.push_back(std::move(commands[i]));
        }
        commands.swap(result); m_Batches.clear();
    }
private:
    std::vector<std::pair<size_t, std::function<std::vector<Command>()>>> m_Batches;
};
#endif
