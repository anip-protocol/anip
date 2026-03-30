using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Routing;
using System.Reflection;

namespace Anip.Studio;

/// <summary>
/// Extension methods to mount ANIP Studio on an ASP.NET Core application.
/// </summary>
public static class AnipStudioExtensions
{
    /// <summary>
    /// Maps ANIP Studio routes at the given prefix (default: /studio).
    /// Serves the embedded SPA with config.json and SPA fallback.
    /// </summary>
    public static IEndpointRouteBuilder MapAnipStudio(
        this IEndpointRouteBuilder app,
        string serviceId,
        string prefix = "/studio")
    {
        var assembly = Assembly.GetExecutingAssembly();
        var resourcePrefix = "Anip.Studio.static.";

        // Config endpoint
        app.MapGet($"{prefix}/config.json", () =>
            Results.Json(new { service_id = serviceId, embedded = true }));

        // Asset files (hashed, immutable cache)
        app.MapGet($"{prefix}/assets/{{file}}", (string file) =>
        {
            var resourceName = $"{resourcePrefix}assets.{file}";
            var stream = assembly.GetManifestResourceStream(resourceName);
            if (stream == null) return Results.NotFound();

            var contentType = file switch
            {
                _ when file.EndsWith(".js") => "application/javascript",
                _ when file.EndsWith(".css") => "text/css",
                _ when file.EndsWith(".json") => "application/json",
                _ when file.EndsWith(".png") => "image/png",
                _ when file.EndsWith(".svg") => "image/svg+xml",
                _ => "application/octet-stream"
            };

            return Results.Stream(stream, contentType);
        });

        // SPA fallback — serve index.html for all other routes
        app.MapGet($"{prefix}/{{**path}}", (string? path) =>
        {
            // Try to serve the exact file
            if (!string.IsNullOrEmpty(path))
            {
                var resourceName = $"{resourcePrefix}{path.Replace('/', '.')}";
                var stream = assembly.GetManifestResourceStream(resourceName);
                if (stream != null)
                    return Results.Stream(stream, "application/octet-stream");
            }

            // Fallback to index.html
            var indexStream = assembly.GetManifestResourceStream($"{resourcePrefix}index.html");
            if (indexStream == null)
                return Results.StatusCode(503);
            return Results.Stream(indexStream, "text/html");
        });

        return app;
    }
}
