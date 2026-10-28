async function init()
{
	const result = await Engine.OpenChildPage("OpenRequest/Entry/Page.xml");

	await new Promise(closePageCallback =>
	{
		globalThis.closePageCallback = () =>
		{
			closePageCallback();
			return result;
		};
	});
}
