/**
 * This class sets up a slider in the developer overlay and assigns its specific handler.
 */
class DeveloperOverlayControlSlider extends DeveloperOverlayControl
{
	constructor(handler, i)
	{
		super(handler, i);

		this.slider = Engine.GetGUIObjectByName("dev_command_slider[" + i + "]");
		this.slider.onValueChange = this.onValueChange.bind(this);
		this.slider.hidden = false;
	}

	onValueChange()
	{
		this.handler.onValueChange(this.slider.value);
		this.update();
	}

	update()
	{
		this.slider.min_value = this.handler.min();
		this.slider.max_value = this.handler.max();
		this.slider.value = this.handler.value();
		this.slider.tooltip = sprintf(translate("%(label)s\n\nValue: %(value)s (min: %(min)s, max: %(max)s)"), {
			"label": this.handler.label(),
			"value": this.handler.value().toFixed(2),
			"min": this.handler.min().toFixed(2),
			"max": this.handler.max().toFixed(2)
		});
		if (this.handler.enabled)
			this.slider.enabled = this.handler.enabled();
	}

	setHidden(hidden)
	{
		if (hidden)
			unregisterSimulationUpdateHandler(this.updater);
		else
			registerSimulationUpdateHandler(this.updater);
	}
}
