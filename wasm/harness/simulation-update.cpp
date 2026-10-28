// Expose the authentic update kernel without constructing the map/debug UI
// facade. Link-time section collection removes unused facade functions.
#include "simulation2/Simulation2.cpp"

void HeadlessUpdateComponents(CSimContext& context, fixed turnLength)
{
    CSimulation2Impl::UpdateComponents(context, turnLength, {});
}
