// Start only the pinned native game in the desktop selected by Computer Use.
// The job accepts a run identifier and fullscreen boolean, never shell text.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Text.RegularExpressions;
using System.Web.Script.Serialization;

internal static class Phase4VisibleNative
{
    [STAThread]
    private static void Main()
    {
        var json = new JavaScriptSerializer();
        string root = Path.GetFullPath(Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "..", ".."));
        string jobs = Path.Combine(root, @"wasm\build\phase4-native-visible");
        var request = json.Deserialize<Dictionary<string, object>>(File.ReadAllText(Path.Combine(jobs, "request.json")));
        string run = (string)request["run"];
        if (!Regex.IsMatch(run, "^[a-f0-9]{32}$")) return;
        bool fullscreen = (bool)request["fullscreen"];
        string directory = Path.Combine(jobs, run);
        Directory.CreateDirectory(directory);
        string status = Path.Combine(directory, "status.json");
        string system = Path.Combine(root, @"wasm\build\native-phase4\binaries\system");
        try
        {
            var start = new ProcessStartInfo(Path.Combine(system, "pyrogenesis.exe"),
                "-writableRoot -mod=public -conf=windowed:" + (!fullscreen).ToString().ToLowerInvariant() +
                " -conf=xres:1920 -conf=yres:1080 -conf=borderless.fullscreen:false -conf=locale:en_US -conf=userreport.enabledversion:0 -conf=vsync:true")
            {
                WorkingDirectory = system, UseShellExecute = false,
                WindowStyle = ProcessWindowStyle.Normal,
                RedirectStandardOutput = true, RedirectStandardError = true
            };
            start.EnvironmentVariables["PHASE4_NATIVE_AUTOMATION"] = directory;
            using (var log = new StreamWriter(Path.Combine(directory, "native.log")))
            using (var process = Process.Start(start))
            {
                log.AutoFlush = true;
                process.OutputDataReceived += (sender, args) => { if (args.Data != null) lock(log) log.WriteLine(args.Data); };
                process.ErrorDataReceived += (sender, args) => { if (args.Data != null) lock(log) log.WriteLine(args.Data); };
                process.BeginOutputReadLine();process.BeginErrorReadLine();
                File.WriteAllText(status, json.Serialize(new { pid = process.Id, exitCode = (int?)null }));
                process.WaitForExit();
                File.WriteAllText(status, json.Serialize(new { pid = process.Id, exitCode = process.ExitCode }));
            }
        }
        catch (Exception error)
        {
            File.WriteAllText(status, json.Serialize(new { error = error.ToString(), exitCode = -1 }));
        }
    }
}
