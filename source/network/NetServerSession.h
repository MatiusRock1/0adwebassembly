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

#ifndef NET_SERVER_SESSION_H
#define NET_SERVER_SESSION_H

#include "network/FSM.h"
#include "network/NetFileTransfer.h"
#include "network/NetHost.h"
#include "ps/CStr.h"

class CNetServerWorker;

typedef struct _ENetPeer ENetPeer;

/**
 * The server's end of a network session.
 * Represents an abstraction of the state of the client, storing all the per-client data
 * needed by the server.
 *
 * Thread-safety:
 * - This is constructed and used by CNetServerWorker in the network server thread.
 */
class CNetServerSession : public CFsm<CNetServerSession, CNetMessage*>
{
	NONCOPYABLE(CNetServerSession);

public:
	CNetServerSession(CNetServerWorker& server, ENetPeer* peer);

	CNetServerWorker& GetServer() { return m_Server; }

	const CStr& GetGUID() const { return m_GUID; }
	void SetGUID(const CStr& guid) { m_GUID = guid; }

	const CStrW& GetUserName() const { return m_UserName; }
	void SetUserName(const CStrW& name) { m_UserName = name; }

	std::uint32_t GetHostID() const { return m_HostID; }
	void SetHostID(std::uint32_t id) { m_HostID = id; }

	std::uint32_t GetIPAddress() const;

	/**
	 * Number of milliseconds since the latest packet of that client was received.
	 */
	std::uint32_t GetLastReceivedTime() const;

	/**
	 * Average round trip time to the client.
	 */
	std::uint32_t GetMeanRTT() const;

	/**
	 * Sends a disconnection notification to the client,
	 * and sends a NMT_CONNECTION_LOST message to the session FSM.
	 * The server will receive a disconnection notification after a while.
	 * The server will not receive any further messages sent via this session.
	 */
	void Disconnect(NetDisconnectReason reason);

	/**
	 * Sends an unreliable disconnection notification to the client.
	 * The server will not receive any disconnection notification.
	 * The server will not receive any further messages sent via this session.
	 */
	void DisconnectNow(NetDisconnectReason reason);

	/**
	 * Send a message to the client.
	 */
	bool SendMessage(const CNetMessage* message);

	CNetFileTransferer& GetFileTransferer() { return m_FileTransferer; }

private:
	CNetServerWorker& m_Server;

	CNetFileTransferer m_FileTransferer;

	ENetPeer* m_Peer;

	CStr m_GUID;
	CStrW m_UserName;
	std::uint32_t m_HostID{0};
	CStr m_Password;
};

#endif // NET_SERVER_SESSION_H
