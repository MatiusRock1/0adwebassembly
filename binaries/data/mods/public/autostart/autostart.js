async function autoStart(cmdLineArgs)
{
	const playerAssignments = {
		"local": {
			"player": +(cmdLineArgs?.['autostart-player'] ?? 1),
			"name": "anonymous",
		},
	};
	const settings = new GameSettings().init();

	// Enable cheats in SP
	settings.cheats.setEnabled(true);

	parseCmdLineArgs(settings, cmdLineArgs);

	settings.launchGame(playerAssignments, !('autostart-disable-replay' in cmdLineArgs));

	return ["page_loading.xml", {
		"attribs": settings.finalizedAttributes,
		"playerAssignments": playerAssignments
	}];
}
