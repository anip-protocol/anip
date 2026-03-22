using Anip.Service;
using Microsoft.Extensions.Hosting;

namespace Anip.AspNetCore;

/// <summary>
/// Bridges the ASP.NET Core hosted service lifecycle to AnipService Start/Shutdown.
/// </summary>
public class AnipLifecycle : IHostedService
{
    private readonly AnipService _service;

    public AnipLifecycle(AnipService service)
    {
        _service = service;
    }

    public Task StartAsync(CancellationToken cancellationToken)
    {
        _service.Start();
        return Task.CompletedTask;
    }

    public Task StopAsync(CancellationToken cancellationToken)
    {
        _service.Shutdown();
        return Task.CompletedTask;
    }
}
