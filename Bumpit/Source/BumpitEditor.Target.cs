using UnrealBuildTool;

public class BumpitEditorTarget : TargetRules
{
    public BumpitEditorTarget(TargetInfo target) : base(target)
    {
        Type = TargetType.Editor;
        DefaultBuildSettings = BuildSettingsVersion.Latest;
        ExtraModuleNames.Add("Bumpit");
    }
}
