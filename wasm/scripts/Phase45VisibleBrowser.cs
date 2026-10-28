// Launch only the phase-4.5 browser in the desktop targeted by Computer Use.
// No shell, input injection or terminal commands are used here.
using System;
using System.Diagnostics;
using System.IO;

internal static class Phase45VisibleBrowser
{
    [STAThread]
    private static void Main()
    {
        string edge = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86),
            @"Microsoft\Edge\Application\msedge.exe");
        string profile = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "0ad-phase45-visible-browser");
        var start = new ProcessStartInfo(edge,
            "--remote-debugging-address=127.0.0.1 --remote-debugging-port=9227 " +
            "--user-data-dir=\"" + profile + "\" --no-first-run --no-default-browser-check " +
            "--force-high-performance-gpu --new-window http://localhost:8095/application.html?automation=1")
        {
            UseShellExecute = false,
            WindowStyle = ProcessWindowStyle.Normal
        };
        using (var browser = Process.Start(start))
            if (browser != null) browser.WaitForExit();
    }
}
