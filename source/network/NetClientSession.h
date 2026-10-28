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

#ifndef NETSESSION_H
#define NETSESSION_H

#include "lib/code_annotation.h"
#include "lib/external_libraries/enet.h"
#include "network/NetFileTransfer.h"
#include "network/NetHost.h"

#include <atomic>
#include <boost/lockfree/queue.hpp>

class CNetClient;
class CNetMessage;
class CNetStatsTable;
class CStr;

typedef struct _ENetHost ENetHost;

/**
 * @file
 * Network client/server sessions.
 *
 * Each session has two classes: CNetClientSession runs on the client,
 * and CNetServerSession runs on the server.
 * A client runs one session at once; a server typically runs many.
 */

/**
 * The client end of a network session.
 * Provides an abstraction of the network interface, allowing communication with the server.
 * The NetClientSession is threaded, so all calls to the public interface must be thread-safe.
 */
class CNetClientSession
{
	NONCOPYABLE(CNetClientSession);

public:
	CNetClientSession(CNetClient& client);
	~CNetClientSession();

	bool Connect(const CStr& server, const std::uint16_t port, ENetHost* enetClient);

	/**
	 * The client NetSession is threaded to avoid getting timeouts if the main thread hangs.
	 * Call Connect() before starting this loop.
	 */
	static void RunNetLoop(CNetClientSession* session);

	/**
	 * Shut down the net session.
	 */
	void Shutdown();

	/**
	 * Processes pending messages.
	 */
	void ProcessPolledMessages();

	/**
	 * Queue up a message to send to the server on the next Loop() call.
	 */
	bool SendMessage(const CNetMessage* message);

	/**
	 * Number of milliseconds since the most recent packet of the server was received.
	 */
	std::uint32_t GetLastReceivedTime() const;

	/**
	 * Average round trip time to the server.
	 */
	std::uint32_t GetMeanRTT() const;

	CNetFileTransferer& GetFileTransferer() { return m_FileTransferer; }
private:
	/**
	 * Process queued incoming messages.
	 */
	void Poll();

	/**
	 * Flush queued outgoing network messages.
	 */
	void Flush();

	CNetClient& m_Client;

	CNetFileTransferer m_FileTransferer;

	// Net messages received and waiting for fetching.
	boost::lockfree::queue<ENetEvent> m_IncomingMessages{16};
	// Net messages to send on the next flush() call.
	boost::lockfree::queue<ENetPacket*> m_OutgoingMessages{16};

	// Last known state. If false, flushing errors are silenced.
	bool m_Connected{false};

	// Whether this session was ever connected to the server.
	bool m_WasConnected{false};

	// Wrapper around enet stats - those are atomic as the code is lock-free.
	std::atomic<std::uint32_t> m_LastReceivedTime{0};
	std::atomic<std::uint32_t> m_MeanRTT{0};

	// If this is true, calling Connect() or deleting the session is an error.
	std::atomic<bool> m_LoopRunning{false};
	std::atomic<bool> m_ShouldShutdown{false};

	std::unique_ptr<ENetHost, DestroyHost> m_Host;
	std::unique_ptr<ENetPeer, DestroyPeer> m_Server;
	std::unique_ptr<CNetStatsTable> m_Stats;
};

#endif	// NETSESSION_H
