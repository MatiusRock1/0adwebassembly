async function autoStartClient(cmdLineArgs)
{
	try
	{
		const playerName = cmdLineArgs['autostart-playername'] || "anonymous";
		const ip = cmdLineArgs['autostart-client'] ?? "127.0.0.1";
		const port = +(cmdLineArgs['autostart-port'] ?? 5073);
		Engine.StartNetworkJoin(playerName, ip, port, !('autostart-disable-replay' in cmdLineArgs));
	}
	catch(e)
	{
		const message = sprintf(translate("Cannot join game: %(message)s."), { "message": e.message });
		messageBox(400, 200, message, translate("Error"));
	}

	let playerAssignments = {};
	while (true)
	{
		const message = await Engine.PollNetworkClient();

		switch (message.type)
		{
		case "players":
			playerAssignments = message.newAssignments;
			Engine.SendNetworkReady(2);
			break;
		case "start":
			return ["page_loading.xml", {
				"attribs": message.initAttributes,
				"isRejoining": true,
				"playerAssignments": playerAssignments
			}];
		default:
		}
	}
}
