/**
 * This class stores the handlers for the individual sliders available in the developer overlay.
 * Such a class must have onSelectionChange function.
 * If the class has a selected property, then that will be called every simulation update to
 * synchronize the state of the slider (only if the developer overaly is opened).
 */
class DeveloperOverlayControlSliders
{
}

DeveloperOverlayControlSliders.prototype.PBRBrightness = class
{
	constructor()
	{
	}

	min()
	{
		return 0.0;
	}

	max()
	{
		return 1.0;
	}

	value()
	{
		return Engine.Renderer_GetPBRBrightness();
	}

	label()
	{
		return translate("PBR brightness");
	}

	onValueChange(value)
	{
		Engine.Renderer_SetPBRBrightness(value);
	}
};
