#if WITH_DEV_AUTOMATION_TESTS
#include "BumpitBoard.h"
#include "PinballTable.h"
#include "Engine/Engine.h"
#include "EngineUtils.h"
#include "Components/StaticMeshComponent.h"
#include "Camera/CameraActor.h"
#include "Misc/AutomationTest.h"

DEFINE_LATENT_AUTOMATION_COMMAND_THREE_PARAMETER(FBumpitWaitForCatch, TWeakObjectPtr<ABumpitBoard>, Board, FAutomationTestBase*, Test, double, Deadline);
bool FBumpitWaitForCatch::Update()
{
    ABumpitBoard* Game = Board.Get();
    if (!Game) { Test->AddError(TEXT("Board disappeared")); return true; }
    if (Game->Phase == ABumpitBoard::EPhase::Flight && FPlatformTime::Seconds()<Deadline) return false;
    Test->TestTrue(TEXT("Shot settled"), Game->Phase == ABumpitBoard::EPhase::Result);
    if (Game->Stage == 1)
    {
        Test->TestTrue(TEXT("Right launch lane feeds scoring field"),Game->Earned>0);
        const FTransform Frame = Game->Table->GetActorTransform();
        const FVector From = Frame.TransformPosition({268,259,16});
        const FVector To = Frame.TransformPosition({268,328,16});
        FHitResult Hit;
        Test->TestTrue(TEXT("Closed gate blocks return to launcher"),
            Game->GetWorld()->LineTraceSingleByChannel(Hit,From,To,ECC_Visibility));
        Game->Advance();
        Test->TestFalse(TEXT("Gate opens for the next ball"),
            Game->GetWorld()->LineTraceSingleByChannel(Hit,From,To,ECC_Visibility));
        Test->TestEqual(TEXT("Stage advanced"),Game->Stage,2);
        Test->TestEqual(TEXT("Purchased bumper retained"),Game->Cells[4],1);
        // Exercise repeated physical contacts with closely spaced obstacles.
        for (int32 Col=0; Col<8; ++Col)
        {
            if (Col!=4) Game->Table->SetObstacle(Col,3);
            Game->Table->SetObstacle(16+Col,1);
        }
        Game->Power = 1;
        Game->Advance();
        return false;
    }
    Test->TestTrue(TEXT("Physical bumper impact scored"),Game->Hits>0);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBumpitPlaytest,"Bumpit.Game.PhysicalRound",
    EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter)
bool FBumpitPlaytest::RunTest(const FString&)
{
    for (const auto& Context : GEngine->GetWorldContexts())
    {
        if (!Context.World() || !Context.World()->IsGameWorld()) continue;
        for (TActorIterator<ABumpitBoard> It(Context.World()); It; ++It)
        {
            ABumpitBoard* Board = *It;
            const FVector Entrance = Board->ViewCamera->GetActorLocation();
            Board->Walk({1,0},.1f);
            TestTrue(TEXT("Walking moves the room camera"),FVector::Distance(Entrance,Board->ViewCamera->GetActorLocation())>40);
            const FVector Eye = Board->ViewCamera->GetActorLocation();
            Board->FocusView(Eye,(FVector::ZeroVector-Eye).GetSafeNormal());
            TestTrue(TEXT("Clicking the machine starts a camera transition"),Board->Blending && Board->Station==ABumpitBoard::EStation::Table);
            Board->UpdateCamera(.25f);
            TestTrue(TEXT("View moves through an intermediate pose"),Board->Blending && !Board->ViewCamera->GetActorLocation().Equals(Eye));
            Board->UpdateCamera(1);
            const FTransform Frame = Board->Table->GetActorTransform();
            const FVector Aim = Frame.TransformPosition({146.25,-253.3124,0});
            const FVector CameraEye = Board->ViewCamera->GetActorLocation();
            const FVector Sight = (Aim-CameraEye).GetSafeNormal();
            TestEqual(TEXT("Hex center can be picked from an angled camera"),Board->Table->PickCell(CameraEye,Sight),0);
            Board->FocusView(CameraEye,Sight);
            Board->UpdateCamera(1);
            TestTrue(TEXT("Focus moves closer to the chosen cell"),FVector::Distance(Board->ViewCamera->GetActorLocation(),Aim)<FVector::Distance(CameraEye,Aim));
            const FVector Notch = Frame.TransformPosition({185,-224,100});
            TestEqual(TEXT("Space outside a hex corner is not selectable"),Board->Table->PickCell(Notch,-Board->Table->GetActorUpVector()),INDEX_NONE);
            Board->Buy(0);
            TestEqual(TEXT("Purchase price"),Board->Credits,9);
            Board->Edit(3,false);
            Board->Edit(3,true);
            Board->Edit(4,false);
            Board->Advance();
            Board->Tick(25.f);
            TestTrue(TEXT("Elapsed time cannot settle an active shot"),Board->Phase == ABumpitBoard::EPhase::Flight);
            ADD_LATENT_AUTOMATION_COMMAND(FBumpitWaitForCatch(Board,this,FPlatformTime::Seconds()+45));
            return true;
        }
    }
    AddError(TEXT("Launch the Bumpit map in game mode to run this test."));
    return false;
}
DEFINE_LATENT_AUTOMATION_COMMAND_THREE_PARAMETER(FCheckRoundBounce, TWeakObjectPtr<APinballTable>, Table, FAutomationTestBase*, Test, double, Deadline);
bool FCheckRoundBounce::Update()
{
    APinballTable* Rig = Table.Get();
    if (!Rig) { Test->AddError(TEXT("Test table disappeared")); return true; }
    if (!Rig->Hits && FPlatformTime::Seconds() < Deadline) return false;
    const FVector Out = Rig->Ball->GetPhysicsLinearVelocity();
    // Half the combined radii gives a 30-degree contact angle.
    const FVector Expected(-.5, FMath::Sqrt(.75), 0);
    Test->TestTrue(TEXT("Offset shot contacted the round bumper"), Rig->Hits > 0);
    Test->TestTrue(TEXT("Exit direction matches circular reflection within 10 degrees"),
        FVector::DotProduct(Out.GetSafeNormal(),Expected) > FMath::Cos(FMath::DegreesToRadians(10.)));
    Test->TestTrue(TEXT("Slow approach receives an outward pinball kick"),Out.Size() >= 440);
    Rig->Destroy();
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FRoundBumperTest,"Bumpit.Game.RoundBumperReflection",
    EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter)
bool FRoundBumperTest::RunTest(const FString&)
{
    for (const auto& Context : GEngine->GetWorldContexts())
    {
        UWorld* World = Context.World();
        if (!World || !World->IsGameWorld()) continue;
        auto* Rig = World->SpawnActor<APinballTable>(FVector(0,0,5000),FRotator::ZeroRotator);
        Rig->SetObstacle(19,1);
        Rig->Launch(0);
        const FVector Center = Rig->Obstacles[19]->GetComponentLocation();
        const double Offset = .5 * (Rig->Obstacles[19]->Bounds.BoxExtent.Y + Rig->Ball->Bounds.BoxExtent.Y);
        Rig->Ball->SetWorldLocation(Center+FVector(-70,Offset,0),false,nullptr,ETeleportType::TeleportPhysics);
        Rig->Ball->SetEnableGravity(false);
        Rig->Ball->SetPhysicsLinearVelocity(FVector(280,0,0));
        ADD_LATENT_AUTOMATION_COMMAND(FCheckRoundBounce(Rig,this,FPlatformTime::Seconds()+5));
        return true;
    }
    AddError(TEXT("A running Bumpit game world is required"));
    return false;
}
#endif
