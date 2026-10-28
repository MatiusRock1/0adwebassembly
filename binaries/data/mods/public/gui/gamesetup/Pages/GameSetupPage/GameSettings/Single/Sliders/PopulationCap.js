const CAPTYPE_PLAYER_POPULATION = "player";
const CAPTYPE_TEAM_POPULATION = "team";
const CAPTYPE_WORLD_POPULATION = "world";

GameSettingControls.PopulationCap = class PopulationCap extends GameSettingControlSlider
{
	constructor(...args)
	{
		super(...args);

		this.sprintfArgs = {};

		g_GameSettings.population.watch(() => this.render(), ["cap", "perPlayer"]);
		g_GameSettings.map.watch(() => this.render(), ["type"]);
		this.render();
	}

	round(value)
	{
		return Math.round(value / 10) * 10;
	}

	linearToLogarythmic(value)
	{
		return this.round((1 / (1 - value) + 28 * value / (1 + 5 * value)) *
			g_GameSettings.population.currentData.Factor / 6);
	}

	render()
	{
		this.setEnabled(g_GameSettings.map.type != "scenario" && !g_GameSettings.population.perPlayer);
		this.title.caption = g_GameSettings.population.currentData.CapTitle;
		if (g_GameSettings.population.perPlayer)
			this.label.caption = this.PerPlayerCaption;
		else
			this.setTooltip(0);

		const linear = this.gameSettingsController.guiData.linearPopulationCapacity ?? 0.5;
		const display = g_GameSettings.population.cap === Infinity ? translate("Unlimited") :
			g_GameSettings.population.cap;
		this.setSelectedValue(linear, display);
	}

	onValueChange(value)
	{
		this.gameSettingsController.guiData.linearPopulationCapacity = value;
		const popCap = this.linearToLogarythmic(value);
		g_GameSettings.population.setPopCap(popCap);
		this.setTooltip(popCap);
		this.gameSettingsController.setNetworkInitAttributes();
	}

	setTooltip(popCap)
	{
		let tooltip = g_GameSettings.population.currentData.CapTooltip;
		if (this.canTotalPopExceedRecommendedMax(popCap))
			tooltip = setStringTags(this.WarningTooltip, this.WarningTags);

		this.slider.tooltip = tooltip;
	}

	canTotalPopExceedRecommendedMax(popCap)
	{
		const nbPlayers = g_GameSettings.playerCount.nbPlayers;
		const nbTeams = g_GameSettings.playerTeam.values.reduce((teamList, team) =>
		{
			if (!teamList.includes(team) || team == -1)
				teamList.push(team);
			return teamList;
		}, []).length;

		switch (g_GameSettings.population.capType)
		{
		case CAPTYPE_PLAYER_POPULATION: return nbPlayers * popCap > this.PopulationCapacityRecommendation;
		case CAPTYPE_TEAM_POPULATION: return nbTeams * popCap > this.PopulationCapacityRecommendation;
		case CAPTYPE_WORLD_POPULATION: return popCap > this.PopulationCapacityRecommendation;
		default: return false;
		}
	}

	onSelectionChange(itemIdx)
	{
		g_GameSettings.population.setPopCap(g_GameSettings.population.currentData.Options.List[itemIdx]);
		this.gameSettingsController.setNetworkInitAttributes();
	}
};

GameSettingControls.PopulationCap.prototype.PerPlayerCaption =
	translateWithContext("population limit", "Per Player");

GameSettingControls.PopulationCap.prototype.WarningTooltip =
	translate("Warning: These settings can result in significant lag when all players reach their maximum population capacity.");

GameSettingControls.PopulationCap.prototype.WarningTags = {
	"color": "orange"
};

/**
 * Total number of units that the engine can run with smoothly.
 * It means a 4v4 with 150 population can still run nicely, but more than that might "lag".
 */
GameSettingControls.PopulationCap.prototype.PopulationCapacityRecommendation = 1200;

GameSettingControls.PopulationCap.prototype.MinValue = 0;
GameSettingControls.PopulationCap.prototype.MaxValue = 1;
