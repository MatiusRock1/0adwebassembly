/**
 * This class manages the button that enables the player to configure the start a new hosted multiplayer match.
 */
class HostButton
{
	constructor(closePageCallback, dialog, xmppMessages, button, loadSavedGame)
	{
		this.hostButton = button;
		this.hostButton.onPress = this.onPress.bind(this, closePageCallback, loadSavedGame);
		this.hostButton.hidden = dialog;

		const onConnectionStatusChange = this.onConnectionStatusChange.bind(this);
		xmppMessages.registerXmppMessageHandler("system", "connected", onConnectionStatusChange);
		xmppMessages.registerXmppMessageHandler("system", "disconnected", onConnectionStatusChange);
		this.onConnectionStatusChange();
	}

	onConnectionStatusChange()
	{
		this.hostButton.enabled = Engine.IsXmppClientConnected();
	}

	async onPress(closePageCallback, loadSavedGame)
	{
		const ret = await Engine.OpenChildPage("page_gamesetup_mp.xml", {
			"loadSavedGame": loadSavedGame,
			"multiplayerGameType": "host",
			"name": g_Nickname,
			"rating": Engine.LobbyGetPlayerRating(g_Nickname)
		});

		if (ret !== undefined)
			closePageCallback({ [Engine.openRequest]: ret });
	}
}
