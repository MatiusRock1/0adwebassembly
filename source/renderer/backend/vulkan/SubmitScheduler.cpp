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

#include "precompiled.h"

#include "SubmitScheduler.h"

#include "lib/debug.h"
#include "ps/CLogger.h"
#include "ps/ConfigDB.h"
#include "renderer/backend/vulkan/Device.h"
#include "renderer/backend/vulkan/RingCommandContext.h"
#include "renderer/backend/vulkan/Utilities.h"

#include <cstddef>
#include <limits>

namespace Renderer
{

namespace Backend
{

namespace Vulkan
{

std::unique_ptr<CSubmitScheduler> CSubmitScheduler::Create(
	CDevice* device, VkQueue queue)
{
	std::unique_ptr<CSubmitScheduler> submitScheduler{new CSubmitScheduler{device, queue}};

	// Currently we need exactly NUMBER_OF_FRAMES_IN_FLIGHT fences to avoid
	// possible overlapping of different work between frames.
	constexpr size_t numberOfFences = NUMBER_OF_FRAMES_IN_FLIGHT;
	submitScheduler->m_Fences.reserve(numberOfFences);
	for (size_t index = 0; index < numberOfFences; ++index)
	{
		VkFenceCreateInfo fenceCreateInfo{};
		fenceCreateInfo.sType = VK_STRUCTURE_TYPE_FENCE_CREATE_INFO;
		VkFence fence = VK_NULL_HANDLE;
		RETURN_NULLPTR_IF_NOT_VK_SUCCESS(vkCreateFence(
			device->GetVkDevice(), &fenceCreateInfo, nullptr, &fence));
		submitScheduler->m_Fences.push_back({fence, INVALID_SUBMIT_HANDLE});
	}
	return submitScheduler;
}

CSubmitScheduler::CSubmitScheduler(CDevice* device, VkQueue queue)
	: m_Device(device), m_Queue(queue)
{
}

CSubmitScheduler::~CSubmitScheduler()
{
	VkDevice device = m_Device->GetVkDevice();

	for (Fence& fence : m_Fences)
		if (fence.value != VK_NULL_HANDLE)
			vkDestroyFence(device, fence.value, nullptr);
}

CSubmitScheduler::SubmitHandle CSubmitScheduler::Submit(VkCommandBuffer commandBuffer)
{
	m_SubmittedCommandBuffers.emplace_back(commandBuffer);
	return m_CurrentHandle;
}

void CSubmitScheduler::WaitUntilFree(const SubmitHandle handle)
{
	// We haven't submitted the current handle.
	if (handle == m_CurrentHandle)
		Flush();

	VkDevice device = m_Device->GetVkDevice();
	while (!m_SubmittedHandles.empty() && handle >= m_SubmittedHandles.front().value)
	{
		Fence& fence = m_Fences[m_SubmittedHandles.front().fenceIndex];
		ENSURE(fence.inUse);
		m_SubmittedHandles.pop();
		ENSURE_VK_SUCCESS(vkWaitForFences(device, 1, &fence.value, VK_TRUE, std::numeric_limits<uint64_t>::max()));
		ENSURE_VK_SUCCESS(vkResetFences(device, 1, &fence.value));
		fence.inUse = false;
		fence.lastUsedHandle = INVALID_SUBMIT_HANDLE;
	}
}

CSubmitScheduler::SubmitHandle CSubmitScheduler::Flush()
{
	ENSURE(!m_SubmittedCommandBuffers.empty());

	Fence& fence = m_Fences[m_FenceIndex];
	if (fence.inUse)
		WaitUntilFree(fence.lastUsedHandle);
	fence.lastUsedHandle = m_CurrentHandle;
	fence.inUse = true;
	m_SubmittedHandles.push({m_CurrentHandle, m_FenceIndex});
	++m_CurrentHandle;
	m_FenceIndex = (m_FenceIndex + 1) % m_Fences.size();

	VkSubmitInfo submitInfo{};
	submitInfo.sType = VK_STRUCTURE_TYPE_SUBMIT_INFO;
	if (!m_NextWaitSemaphores.empty())
	{
		ENSURE(m_NextWaitSemaphores.size() == m_NextWaitDstStageMasks.size());
		submitInfo.waitSemaphoreCount = m_NextWaitSemaphores.size();
		submitInfo.pWaitSemaphores = m_NextWaitSemaphores.data();
		submitInfo.pWaitDstStageMask = m_NextWaitDstStageMasks.data();
	}
	if (!m_NextSubmitSignalSemaphores.empty())
	{
		submitInfo.signalSemaphoreCount = m_NextSubmitSignalSemaphores.size();
		submitInfo.pSignalSemaphores = m_NextSubmitSignalSemaphores.data();
	}
	submitInfo.commandBufferCount = m_SubmittedCommandBuffers.size();
	submitInfo.pCommandBuffers = m_SubmittedCommandBuffers.data();

	ENSURE_VK_SUCCESS(vkQueueSubmit(m_Queue, 1, &submitInfo, fence.value));

	m_NextWaitSemaphores.clear();
	m_NextWaitDstStageMasks.clear();
	m_NextSubmitSignalSemaphores.clear();

	m_SubmittedCommandBuffers.clear();

	return fence.lastUsedHandle;
}

void CSubmitScheduler::EnqueueWaitOnNextSubmit(
	VkSemaphore semaphore, const VkPipelineStageFlags stageMask)
{
	m_NextWaitSemaphores.emplace_back(semaphore);
	m_NextWaitDstStageMasks.emplace_back(stageMask);
}

void CSubmitScheduler::EnqueueSignalOnNextSubmit(
	VkSemaphore semaphore)
{
	m_NextSubmitSignalSemaphores.emplace_back(semaphore);
}

} // namespace Vulkan

} // namespace Backend

} // namespace Renderer
