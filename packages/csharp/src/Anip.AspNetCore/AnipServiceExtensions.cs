using System.Text.Json;
using System.Text.Json.Serialization;
using Anip.Service;
using Microsoft.Extensions.DependencyInjection;

namespace Anip.AspNetCore;

/// <summary>
/// Extension methods for registering ANIP services with the ASP.NET Core DI container.
/// </summary>
public static class AnipServiceExtensions
{
    /// <summary>
    /// Registers the AnipService, lifecycle management, and controller with DI.
    /// Configures JSON serialization with snake_case naming.
    /// </summary>
    public static IServiceCollection AddAnip(
        this IServiceCollection services,
        AnipService anipService,
        Action<AnipOptions>? configureOptions = null)
    {
        var options = new AnipOptions();
        configureOptions?.Invoke(options);

        services.AddSingleton(anipService);
        services.AddSingleton(options);
        services.AddHostedService<AnipLifecycle>();
        services.AddControllers()
            .AddJsonOptions(opts =>
            {
                opts.JsonSerializerOptions.PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower;
                opts.JsonSerializerOptions.DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull;
            })
            .AddApplicationPart(typeof(AnipController).Assembly);

        return services;
    }
}
