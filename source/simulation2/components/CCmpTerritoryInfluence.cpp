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

#include "ICmpTerritoryInfluence.h"

#include "simulation2/components/ICmpValueModificationManager.h"
#include "simulation2/system/Component.h"

#include <string>

class CCmpTerritoryInfluence final : public ICmpTerritoryInfluence
{
public:
	static void ClassInit(CComponentManager&)
	{
	}

	DEFAULT_COMPONENT_ALLOCATOR(TerritoryInfluence)

	bool m_Root;
	std::uint16_t m_Weight;
	std::uint32_t m_Radius;

	static std::string GetSchema()
	{
		return
			"<element name='Root'>"
				"<data type='boolean'/>"
			"</element>"
			"<element name='Weight'>"
				"<data type='nonNegativeInteger'>"
					"<param name='maxInclusive'>65535</param>" // Max std::uint16_t value
				"</data>"
			"</element>"
			"<element name='Radius'>"
				"<data type='nonNegativeInteger'/>"
			"</element>";
	}

	void Init(const CParamNode& paramNode) override
	{
		m_Root = paramNode.GetChild("Root").ToBool();
		m_Weight = static_cast<std::uint16_t>(paramNode.GetChild("Weight").ToInt());
		m_Radius = paramNode.GetChild("Radius").ToInt();
	}

	void Deinit() override
	{
	}

	void Serialize(ISerializer&) override
	{
	}

	void Deserialize(const CParamNode& paramNode, IDeserializer&) override
	{
		Init(paramNode);
	}

	bool IsRoot() const override
	{
		CmpPtr<ICmpValueModificationManager> cmpValueModificationManager(GetSystemEntity());
		if (!cmpValueModificationManager)
			return m_Root;

		return cmpValueModificationManager->ApplyModifications(L"TerritoryInfluence/Root", m_Root, GetEntityId());
	}

	std::uint16_t GetWeight() const override
	{
		CmpPtr<ICmpValueModificationManager> cmpValueModificationManager(GetSystemEntity());
		if (!cmpValueModificationManager)
			return m_Weight;

		return cmpValueModificationManager->ApplyModifications(L"TerritoryInfluence/Weight", m_Weight, GetEntityId());
	}

	std::uint32_t GetRadius() const override
	{
		CmpPtr<ICmpValueModificationManager> cmpValueModificationManager(GetSystemEntity());
		if (!cmpValueModificationManager)
			return m_Radius;

		std::uint32_t newRadius = cmpValueModificationManager->ApplyModifications(L"TerritoryInfluence/Radius", m_Radius, GetEntityId());
		return newRadius;
	}
};

REGISTER_COMPONENT_TYPE(TerritoryInfluence)
