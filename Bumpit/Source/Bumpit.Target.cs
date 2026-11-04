using UnrealBuildTool;

public class BumpitTarget : TargetRules
{
    public BumpitTarget(TargetInfo target) : base(target)
    {
        Type = TargetType.Game;
        DefaultBuildSettings = BuildSettingsVersion.Latest;
        ExtraModuleNames.Add("Bumpit");
    }
}
