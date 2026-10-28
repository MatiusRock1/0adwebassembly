#include "../experiments/timer-monotonic/application-timer-monotonic.h"

#include <bit>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <limits>
#include <mutex>
#include <thread>
#include <vector>

class ReferenceClock
{
public:
	double Publish(double observed)
	{
		std::lock_guard<std::mutex> lock(m_Mutex);
		m_Maximum = std::max(m_Maximum, observed);
		return m_Maximum;
	}
private:
	std::mutex m_Mutex;
	double m_Maximum = 0.0;
};

bool CheckSequence(const std::vector<double>& values)
{
	ReferenceClock reference;
	WasmApplication::MonotonicClock actual;
	for (double value : values)
		if (std::bit_cast<std::uint64_t>(reference.Publish(value)) !=
			std::bit_cast<std::uint64_t>(actual.Publish(value)))
			return false;
	return true;
}

template<typename Clock>
bool CheckConcurrent(int threads, double& milliseconds)
{
	Clock clock;
	std::atomic<unsigned> failures{0};
	std::atomic<unsigned> ready{0};
	std::atomic<bool> start{false};
	constexpr unsigned iterations = 100000;
	std::vector<std::thread> workers;
	for (int id = 0; id < threads; ++id)
		workers.emplace_back([&, id]()
		{
			ready.fetch_add(1);
			while (!start.load())
				std::this_thread::yield();
			double last = 0.0;
			for (unsigned i = 0; i < iterations; ++i)
			{
				const double input = double(i * threads + id + 1);
				const double current = clock.Publish(input);
				const double backwards = clock.Publish(-input);
				if (current < input || current < last || backwards < current || !std::isfinite(backwards))
					failures.fetch_add(1);
				last = backwards;
			}
		});
	while (ready.load() != unsigned(threads))
		std::this_thread::yield();
	const auto began = std::chrono::steady_clock::now();
	start.store(true);
	for (auto& worker : workers)
		worker.join();
	milliseconds = std::chrono::duration<double, std::milli>(
		std::chrono::steady_clock::now() - began).count();
	return failures.load() == 0 && clock.Publish(0.0) == iterations * threads;
}

int main()
{
	const double nan = std::numeric_limits<double>::quiet_NaN();
	const double inf = std::numeric_limits<double>::infinity();
	const std::vector<std::vector<double>> sequences{
		{0, 1e-9, 0.1, 1.0, 1e20},
		{5, 4, 3, 2, 1, 0, -1},
		{1, 1, 1, 2, 2},
		{-0.0, +0.0, -0.0},
		{nan, -nan, 7, nan, 3, 9, nan},
		{1, inf, 2, inf, nan},
		{-inf, -1, -0.0, 1, -inf}
	};
	unsigned checks = 0;
	for (const auto& sequence : sequences)
	{
		if (!CheckSequence(sequence))
			return 1;
		++checks;
	}
	std::printf("{\"diagnosticOnly\":true,\"performanceAcceptance\":false,\"concurrency\":[");
	for (int threads : {2, 4, 8})
	{
		double referenceMs, atomicMs;
		if (!CheckConcurrent<ReferenceClock>(threads, referenceMs) ||
			!CheckConcurrent<WasmApplication::MonotonicClock>(threads, atomicMs))
			return 2;
		std::printf("%s{\"threads\":%d,\"callsPerClock\":%d,\"mutexMs\":%.3f,\"atomicMs\":%.3f}",
			threads == 2 ? "" : ",", threads, threads * 200000, referenceMs, atomicMs);
		++checks;
	}
	std::printf("],\"passed\":true,\"checks\":%u,\"lockFree\":true}\n", checks);
	return 0;
}
