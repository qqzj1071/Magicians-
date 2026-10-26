namespace Magicians.Core.Combat;

public enum ActionValueResolutionStep
{
    PoisonDamageAndDecay = 10,
    TemporaryStatusExpiry = 20,
    Fatigue = 30,
    FirePreparation = 40,
    SynchronizedProjectiles = 50,
    DeathCheck = 60,
    Draw = 70,
    PlayerActions = 80
}
