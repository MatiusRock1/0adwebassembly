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

#include "SwapChain.h"

#include "renderer/backend/dummy/Device.h"
#include "renderer/backend/dummy/Framebuffer.h"

namespace Renderer
{

namespace Backend
{

namespace Dummy
{

// static
std::unique_ptr<ISwapChain> CSwapChain::Create(CDevice* device)
{
	std::unique_ptr<CSwapChain> swapChain(new CSwapChain());
	swapChain->m_Device = device;
	swapChain->m_Backbuffer =
		device->CreateFramebuffer("Backbuffer", nullptr, nullptr);
	return swapChain;
}

CSwapChain::CSwapChain() = default;

CSwapChain::~CSwapChain() = default;

IDevice* CSwapChain::GetDevice()
{
	return m_Device;
}

bool CSwapChain::AcquireNextBackbuffer()
{
	// We have nothing to acquire.
	return true;
}

IFramebuffer* CSwapChain::GetCurrentBackbuffer(
	const AttachmentLoadOp, const AttachmentStoreOp,
	const AttachmentLoadOp, const AttachmentStoreOp)
{
	return m_Backbuffer.get();
}

void CSwapChain::Present()
{
	// We have nothing to present.
}

} // namespace Dummy

} // namespace Backend

} // namespace Renderer
