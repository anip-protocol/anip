using System.Threading.Channels;

namespace Anip.Service;

/// <summary>
/// Holds a channel of streaming events.
/// The channel is closed after exactly one terminal event (completed or failed).
/// Call Cancel() to signal the handler that the client has disconnected.
/// </summary>
public class StreamResult
{
    public ChannelReader<StreamEvent> Events { get; }
    public Action Cancel { get; }

    public StreamResult(ChannelReader<StreamEvent> events, Action cancel)
    {
        Events = events;
        Cancel = cancel;
    }
}
