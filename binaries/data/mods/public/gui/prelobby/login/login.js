function init()
{
	Engine.GetGUIObjectByName("continue").caption = translate("Connect");

	// Shorten the displayed password for visual reasons only
	Engine.GetGUIObjectByName("username").caption = Engine.ConfigDB_GetValue("user", "lobby.login");
	Engine.GetGUIObjectByName("password").caption = Engine.ConfigDB_GetValue("user", "lobby.password").substr(0, 10);

	initLobbyTerms();

	initRememberPassword();

	updateFeedback();

	return Promise.race([ onLoggedin(), cancelButton() ]);
}

function updateFeedback()
{
	setFeedback(checkUsername(false) || checkPassword(false) || checkTerms());
}

// Remember which user agreed to the terms
function onUsernameEdit()
{
	loadTermsAcceptance();
	updateFeedback();
}

function continueButton()
{
	setFeedback(translate("Connecting…"));

	Engine.StartXmppClient(
		Engine.GetGUIObjectByName("username").caption,
		getEncryptedPassword(),
		Engine.ConfigDB_GetValue("user", "lobby.room"),
		Engine.GetGUIObjectByName("username").caption,
		+Engine.ConfigDB_GetValue("user", "lobby.history"));

	Engine.ConnectXmppClient();
}

async function onLoggedin()
{
	await new Promise(resolve => { g_LobbyMessages.connected = resolve; });
	saveCredentials();

	// The data from Engine.SendGetBoardList() is used for the leaderboard, but also for
	// autocompletion in the profile player search field.
	Engine.SendGetBoardList();
	return {
		"page": "page_lobby.xml",
		"argument": {
			"dialog": false
		}
	};
}
