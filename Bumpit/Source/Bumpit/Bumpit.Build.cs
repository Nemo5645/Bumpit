using UnrealBuildTool;

public class Bumpit : ModuleRules
{
    public Bumpit(ReadOnlyTargetRules target) : base(target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new[] { "Core", "CoreUObject", "Engine", "InputCore", "PhysicsCore" });
        if (target.bBuildEditor) PrivateDependencyModuleNames.AddRange(new[] { "UnrealEd", "BlueprintGraph", "SlateCore" });
    }
}
