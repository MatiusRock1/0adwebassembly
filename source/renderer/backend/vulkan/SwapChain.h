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

#ifndef INCLUDED_RENDERER_BACKEND_VULKAN_SWAPCHAIN
#define INCLUDED_RENDERER_BACKEND_VULKAN_SWAPCHAIN

#include "renderer/backend/IFramebuffer.h"
#include "renderer/backend/ISwapChain.h"
#include "renderer/backend/vulkan/SubmitScheduler.h"

#include <cstddef>
#include <cstdint>
#include <glad/vulkan.h>
#include <limits>
#include <memory>
#include <tuple>
#include <unordered_map>
#include <vector>

namespace Renderer::Backend::Vulkan { class CDevice; }
namespace Renderer::Backend::Vulkan { class CFramebuffer; }
namespace Renderer::Backend::Vulkan { class CRingCommandContext; }
namespace Renderer::Backend::Vulkan { class CTexture; }

namespace Renderer
{

namespace Backend
{

namespace Vulkan
{

class CSwapChain final : public ISwapChain
{
public:
	~CSwapChain() override;

	IDevice* GetDevice() override;

	bool IsValid() const override { return m_IsValid; }

	bool AcquireNextBackbuffer() override;

	IFramebuffer* GetCurrentBackbuffer(
		const AttachmentLoadOp colorAttachmentLoadOp,
		const AttachmentStoreOp colorAttachmentStoreOp,
		const AttachmentLoadOp depthStencilAttachmentLoadOp,
		const AttachmentStoreOp depthStencilAttachmentStoreOp) override;

	void Present() override;

	VkSwapchainKHR GetVkSwapchain() { return m_SwapChain; }

	bool AcquireNextImage();
	void SubmitCommandsAfterAcquireNextImage(
		CRingCommandContext& commandContext);
	void SubmitCommandsBeforePresent(
		CRingCommandContext& commandContext);
	void Present(VkSemaphore submitDone, VkQueue queue);

	CTexture* GetCurrentBackbufferTexture();

	CTexture* GetOrCreateBackbufferReadbackTexture();

	CTexture* GetDepthTexture() { return m_DepthTexture.get(); }

private:
	friend class CDevice;

	static std::unique_ptr<CSwapChain> Create(
		CDevice* device, CSubmitScheduler* submitScheduler,
		const uint32_t queueFamilyIndex, VkQueue queue,
		const char* name, VkSurfaceKHR surface,
		int surfaceDrawableWidth, int surfaceDrawableHeight,
		const bool vsync, std::unique_ptr<ISwapChain> oldSwapChain);

	CSwapChain();

	CDevice* m_Device = nullptr;
	CSubmitScheduler* m_SubmitScheduler{nullptr};
	VkQueue m_Queue{VK_NULL_HANDLE};

	bool m_IsValid = false;
	VkSwapchainKHR m_SwapChain = VK_NULL_HANDLE;

	uint32_t m_CurrentImageIndex = std::numeric_limits<uint32_t>::max();

	std::vector<VkImage> m_Images;
	std::vector<std::unique_ptr<CTexture>> m_Textures;
	std::unique_ptr<CTexture> m_DepthTexture;
	VkFormat m_ImageFormat = VK_FORMAT_UNDEFINED;

	uint32_t m_FrameID{0};

	// We can't reuse the same acquire semaphore immediately after present
	// because it might still be processing on GPU as vkQueuePresentKHR doesn't
	// have to be blocking.
	// We need to wait for the image on GPU to draw to it.
	struct FrameObject
	{
		VkSemaphore acquireImageSemaphore{VK_NULL_HANDLE};
		// We need to know when we can reuse the semaphore.
		CSubmitScheduler::SubmitHandle submitHandle{CSubmitScheduler::INVALID_SUBMIT_HANDLE};
	};
	std::vector<FrameObject> m_FrameObjects;

	// The number of submit semaphores should be equal to the number of images
	// in the swapchain. We could use NUMBER_OF_FRAMES_IN_FLIGHT of objects but
	// it might be not safe. Since vkQueuePresentKHR doesn't provide a way to
	// tell that a semaphore was signaled.
	//
	// A possible situation, list of acquired indices:
	//  0, 1, 2, 0, 1, 0, 1
	//                     ^
	// In theory in the end we might still have a semaphore in use for the
	// 2nd swapchain image.
	//
	// See also:
	//  https://docs.vulkan.org/guide/latest/swapchain_semaphore_reuse.html
	// We need to present only after all submit work is done.
	std::vector<VkSemaphore> m_SubmitSemaphores;

	struct SwapChainBackbuffer
	{
		using BackbufferKey = std::tuple<
			AttachmentLoadOp, AttachmentStoreOp,
			AttachmentLoadOp, AttachmentStoreOp>;
		struct BackbufferKeyHash
		{
			size_t operator()(const BackbufferKey& key) const;
		};
		std::unordered_map<
			BackbufferKey, std::unique_ptr<CFramebuffer>, BackbufferKeyHash> backbuffers;

		SwapChainBackbuffer();

		SwapChainBackbuffer(const SwapChainBackbuffer&) = delete;
		SwapChainBackbuffer& operator=(const SwapChainBackbuffer&) = delete;

		SwapChainBackbuffer(SwapChainBackbuffer&& other);
		SwapChainBackbuffer& operator=(SwapChainBackbuffer&& other);
	};
	std::vector<SwapChainBackbuffer> m_Backbuffers;

	std::unique_ptr<CTexture> m_BackbufferReadbackTexture;

	std::unique_ptr<CRingCommandContext> m_AcquireCommandContext;
	std::unique_ptr<CRingCommandContext> m_PresentCommandContext;

	bool m_DebugWaitIdleBeforeAcquire = false;
	bool m_DebugWaitIdleBeforePresent = false;
	bool m_DebugWaitIdleAfterPresent = false;
};

} // namespace Vulkan

} // namespace Backend

} // namespace Renderer

#endif // INCLUDED_RENDERER_BACKEND_VULKAN_SWAPCHAIN
