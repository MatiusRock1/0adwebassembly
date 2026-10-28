async function autoStartHost(cmdLineArgs)
{
	const maxPlayers = +(cmdLineArgs['autostart-host-players'] ?? 2);

	try
	{
		const playerName = cmdLineArgs['autostart-playername'] || "anonymous";
		const port = +(cmdLineArgs['autostart-port'] ?? 5073);

		// Password not implemented for autostart.
		Engine.StartNetworkHost(playerName, port, "", false, !('autostart-disable-replay' in cmdLineArgs));
	}
	catch(e)
	{
		const message = sprintf(translate("Cannot host game: %(message)s."), { "message": e.message });
		messageBox(400, 200, message, translate("Error"));
	}

	/**
	 * Handles a simple implementation of player assignments.
	 * Should not need be overloaded in mods unless you want to change that logic.
	 */

	let playerAssignments = {};
	while (true)
	{
		const message = await Engine.PollNetworkClient();
		switch (message.type)
		{
		case "players":
		{
			playerAssignments = message.newAssignments;
			Engine.SendNetworkReady(2);
			let max = 0;
			for (const uid in playerAssignments)
			{
				max = Math.max(playerAssignments[uid].player, max);
				if (playerAssignments[uid].player == -1)
					Engine.AssignNetworkPlayer(++max, uid);
			}
			break;
		}
		case "ready":
			playerAssignments[message.guid].status = message.status;
			break;
		default:
		}

		const assignementArray = Object.values(playerAssignments);
		if (assignementArray.length === maxPlayers &&
			assignementArray.every(assignement =>
				assignement.player !== -1 || assignement.status !== 0))
		{
			break;
		}
	}

	const settings = new GameSettings().init();

	parseCmdLineArgs(settings, cmdLineArgs);

	settings.playerCount.setNb(Object.keys(playerAssignments).length);
	settings.launchGame(playerAssignments, false);

	while ((await Engine.PollNetworkClient()).type !== "start")
	{
		// Just wait for condition
	}

	return ["page_loading.xml", {
		"attribs": settings.finalizedAttributes,
		"playerAssignments": playerAssignments
	}];
}
