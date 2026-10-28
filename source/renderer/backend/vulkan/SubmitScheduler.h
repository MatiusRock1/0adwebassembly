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

#ifndef INCLUDED_RENDERER_BACKEND_VULKAN_SUBMITSCHEDULER
#define INCLUDED_RENDERER_BACKEND_VULKAN_SUBMITSCHEDULER

#include "renderer/backend/vulkan/Device.h"

#include <array>
#include <cstdint>
#include <glad/vulkan.h>
#include <memory>
#include <queue>
#include <vector>

namespace Renderer::Backend::Vulkan { class CRingCommandContext; }

namespace Renderer
{

namespace Backend
{

namespace Vulkan
{

/**
 * A helper class to batch VkQueueSubmit calls and track VkCommandBuffer usages
 * properly.
 */
class CSubmitScheduler
{
public:
	using SubmitHandle = uint32_t;
	static constexpr SubmitHandle INVALID_SUBMIT_HANDLE = 0;

	static std::unique_ptr<CSubmitScheduler> Create(
		CDevice* device, VkQueue queue);
	~CSubmitScheduler();

	SubmitHandle Submit(VkCommandBuffer commandBuffer);

	void WaitUntilFree(const SubmitHandle handle);

	uint32_t GetFrameID() const { return m_FrameID; }

	SubmitHandle Flush();

	/**
	 * It's a caller responsibility to guarantee a semaphore lifespan.
	 */
	void EnqueueWaitOnNextSubmit(VkSemaphore semaphore, const VkPipelineStageFlags stageMask);
	void EnqueueSignalOnNextSubmit(VkSemaphore semaphore);

private:
	CSubmitScheduler(CDevice* device, VkQueue queue);

	CDevice* m_Device = nullptr;
	VkQueue m_Queue = VK_NULL_HANDLE;

	struct Fence
	{
		VkFence value = VK_NULL_HANDLE;
		SubmitHandle lastUsedHandle = INVALID_SUBMIT_HANDLE;
		bool inUse = false;
	};
	std::vector<Fence> m_Fences;
	uint32_t m_FenceIndex = 0;

	// We assume that we won't run so long that the frame ID will overflow.
	uint32_t m_FrameID = 0;
	SubmitHandle m_CurrentHandle = INVALID_SUBMIT_HANDLE + 1;
	struct SubmittedHandle
	{
		SubmitHandle value;
		uint32_t fenceIndex;
	};
	std::queue<SubmittedHandle> m_SubmittedHandles;

	std::vector<VkSemaphore> m_NextWaitSemaphores;
	std::vector<VkPipelineStageFlags> m_NextWaitDstStageMasks;
	std::vector<VkSemaphore> m_NextSubmitSignalSemaphores;

	std::vector<VkCommandBuffer> m_SubmittedCommandBuffers;
};

} // namespace Vulkan

} // namespace Backend

} // namespace Renderer

#endif // INCLUDED_RENDERER_BACKEND_VULKAN_SUBMITSCHEDULER
