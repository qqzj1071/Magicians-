namespace Magicians.Core.Common;

public sealed record Rejection(string Code, string Message);

public sealed record CommandResult<TState>(
    bool Accepted,
    TState State,
    IReadOnlyList<GameEvent> Events,
    Rejection? Rejection,
    string StateHash
);
