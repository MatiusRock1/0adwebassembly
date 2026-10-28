#ifndef INCLUDED_WASM_APPLICATION_TIMER_MONOTONIC
#define INCLUDED_WASM_APPLICATION_TIMER_MONOTONIC

#include <algorithm>
#include <atomic>

namespace WasmApplication
{
// Preserve timer.cpp's max(previous, observed) clamp, including NaN and -0.
// Only the maximum is shared; this clock does not publish other application data.
class MonotonicClock
{
public:
	static_assert(std::atomic<double>::is_always_lock_free,
		"This experiment requires native lock-free double atomics");

	double Publish(double observed)
	{
		double previous = m_Maximum.load(std::memory_order_relaxed);
		while (previous < observed && !m_Maximum.compare_exchange_weak(
			previous, observed, std::memory_order_relaxed, std::memory_order_relaxed))
		{
		}
		return std::max(previous, observed);
	}

private:
	std::atomic<double> m_Maximum{0.0};
};
}

#endif
