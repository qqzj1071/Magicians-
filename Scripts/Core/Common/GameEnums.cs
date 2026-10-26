namespace Magicians.Core.Common;

public enum PlayerKind
{
    Human,
    Ai,
    Ghost
}

public enum MatchPhase
{
    Setup,
    // Pairings are published before the next draft begins.
    Draft,
    Pairing,
    Combat,
    Settlement,
    Finished
}
