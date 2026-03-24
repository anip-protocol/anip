using Anip.Service;

namespace Anip.Stdio;

/// <summary>
/// Convenience entry point that manages the AnipService lifecycle and runs the stdio server.
/// </summary>
public static class AnipStdioRunner
{
    /// <summary>
    /// Starts the service, runs the stdio server until cancellation or EOF, then shuts down.
    /// </summary>
    public static async Task RunAsync(AnipService service, CancellationToken ct = default)
    {
        service.Start();
        try
        {
            var server = new AnipStdioServer(service);
            await server.ServeAsync(ct);
        }
        finally
        {
            service.Shutdown();
        }
    }
}
