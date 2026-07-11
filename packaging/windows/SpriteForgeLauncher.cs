using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

public static class SpriteForgeLauncher {
  private static string Quote(string value) { return "\"" + value.Replace("\"", "\\\"") + "\""; }
  [STAThread]
  public static int Main(string[] args) {
    string root = AppContext.BaseDirectory;
    string python = Path.Combine(root, "runtime", "pythonw.exe");
    string script = Path.Combine(root, "app", "spriteforge_launcher.py");
    if (!File.Exists(python) || !File.Exists(script)) {
      MessageBox.Show("SpriteForge runtime is incomplete. Run Repair from Windows Apps settings.", "SpriteForge Studio", MessageBoxButtons.OK, MessageBoxIcon.Error);
      return 2;
    }
    string arguments = Quote(script);
    foreach (string arg in args) arguments += " " + Quote(arg);
    var start = new ProcessStartInfo(python, arguments) { UseShellExecute = false, WorkingDirectory = Path.Combine(root, "app") };
    start.EnvironmentVariables["SPRITEFORGE_RUNTIME_PYTHON"] = Path.Combine(root, "runtime", "python.exe");
    using (var process = Process.Start(start)) { process.WaitForExit(); return process.ExitCode; }
  }
}
