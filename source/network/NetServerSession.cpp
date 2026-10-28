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

#include "NetServerSession.h"

#include "lib/external_libraries/enet.h"
#include "network/NetMessage.h"
#include "network/NetMessages.h"
#include "network/NetServer.h"
#include "ps/CLogger.h"

CNetServerSession::CNetServerSession(CNetServerWorker& server, ENetPeer* peer) :
	m_Server(server), m_FileTransferer(*this), m_Peer(peer)
{
}

std::uint32_t CNetServerSession::GetIPAddress() const
{
	return m_Peer->address.host;
}

std::uint32_t CNetServerSession::GetLastReceivedTime() const
{
	if (!m_Peer)
		return 0;

	return enet_time_get() - m_Peer->lastReceiveTime;
}

std::uint32_t CNetServerSession::GetMeanRTT() const
{
	if (!m_Peer)
		return 0;

	return m_Peer->roundTripTime;
}

void CNetServerSession::Disconnect(NetDisconnectReason reason)
{
	if (reason == NDR_UNKNOWN)
		LOGWARNING("Disconnecting client without communicating the disconnect reason!");

	Update(static_cast<unsigned int>(NMT_CONNECTION_LOST), nullptr);

	enet_peer_disconnect(m_Peer, static_cast<enet_uint32>(reason));
}

void CNetServerSession::DisconnectNow(NetDisconnectReason reason)
{
	if (reason == NDR_UNKNOWN)
		LOGWARNING("Disconnecting client without communicating the disconnect reason!");

	enet_peer_disconnect_now(m_Peer, static_cast<enet_uint32>(reason));
}

bool CNetServerSession::SendMessage(const CNetMessage* message)
{
	return m_Server.SendMessage(m_Peer, message);
}
