#include "PinballTable.h"
#include "Components/StaticMeshComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "PhysicalMaterials/PhysicalMaterial.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
const FLinearColor Slate(.035,.09,.14), Edge(.10,.23,.30), Aqua(.05,.85,.65), Amber(1,.54,.08), Rose(.96,.19,.11);
constexpr float Width = 576;
constexpr double DividerY = 294., DividerThickness = 10., BallRadius = 9.;
const FVector LaunchPosition(-269,330,BallRadius+1.);
constexpr double HexRadius = 39.;
constexpr double RootThree = 1.7320508075688772;
FVector HexCenter(int32 Index)
{
    const int32 Row = Index / 8;
    return FVector((2.5 - Row) * 1.5 * HexRadius,
        (Index % 8 - 3.75 + .5 * (Row % 2)) * RootThree * HexRadius, 0);
}
}

APinballTable::APinballTable()
{
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.bStartWithTickEnabled = false;
    PrimaryActorTick.TickGroup = TG_PrePhysics;
    RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Table frame"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Box(TEXT("/Engine/BasicShapes/Cube"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Drum(TEXT("/Engine/BasicShapes/Cylinder"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Marble(TEXT("/Engine/BasicShapes/Sphere"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> Paint(TEXT("/Engine/BasicShapes/BasicShapeMaterial"));
    Cube = Box.Object; Cylinder = Drum.Object; Sphere = Marble.Object; Surface = Paint.Object;
}

UStaticMeshComponent* APinballTable::Piece(UStaticMesh* Mesh, FVector Pos, FVector Size, FLinearColor Color, bool Solid, float Yaw)
{
    auto* Part = NewObject<UStaticMeshComponent>(this);
    AddInstanceComponent(Part);
    Part->SetupAttachment(RootComponent);
    Part->SetStaticMesh(Mesh);
    Part->SetRelativeLocation(Pos);
    Part->SetRelativeRotation(FRotator(0,Yaw,0));
    Part->SetRelativeScale3D(Size/100.);
    Part->SetCollisionProfileName(Solid ? TEXT("BlockAllDynamic") : TEXT("NoCollision"));
    Part->SetPhysMaterialOverride(Rubber);
    auto* Paint = UMaterialInstanceDynamic::Create(Surface,this);
    Paint->SetVectorParameterValue(TEXT("Color"),Color);
    Part->SetMaterial(0,Paint);
    Part->RegisterComponent();
    return Part;
}

void APinballTable::BeginPlay()
{
    Super::BeginPlay();
    BuildGeometry();
}

void APinballTable::BuildGeometry()
{
    if (Ball) return;
    Rubber = NewObject<UPhysicalMaterial>(this);
    Rubber->Friction = .22f;
    Rubber->Restitution = .58f;
    Obstacles.SetNumZeroed(48);
    Piece(Cube,{0,0,-13},{722,Width+18,26},Slate);
    Piece(Cube,{0,-294,15},{724,12,54},Edge);
    Piece(Cube,{-58,DividerY,15},{600,DividerThickness,54},Edge);
    LaunchGate = Piece(Cube,{302,DividerY,15},{120,DividerThickness,54},Amber);
    SetLaunchGateClosed(false);
    Piece(Cube,{0,373,15},{724,12,54},Edge);
    Piece(Cube,{0,330,-13},{722,82,26},Slate);
    Piece(Cube,{286,330,18},{116,14,44},Edge,true,-45);
    Piece(Cube,{-344,330,15},{16,82,50},Edge);
    Piece(Cube,{-313,331,8},{45,10,16},Amber,false);
    Piece(Cube,{356,0,15},{12,Width,54},Edge);
    Piece(Cube,{-356,0,15},{12,Width,54},Edge);
    auto* Grid = NewObject<UInstancedStaticMeshComponent>(this,TEXT("HexGrid"));
    AddInstanceComponent(Grid);
    Grid->SetupAttachment(RootComponent);
    Grid->SetStaticMesh(Cube);
    Grid->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Grid->SetCastShadow(false);
    auto* Lines = UMaterialInstanceDynamic::Create(Surface,this);
    Lines->SetVectorParameterValue(TEXT("Color"),Edge);
    Grid->SetMaterial(0,Lines);
    Grid->RegisterComponent();
    for (int32 Index=0; Index<Obstacles.Num(); ++Index)
    {
        // Inset the outline slightly so adjacent cells have separate, non-overlapping edges.
        for (int32 Side=0; Side<6; ++Side)
        {
            const double Angle = 30. + Side * 60.;
            const FVector Mid = HexCenter(Index) + FRotator(0,Angle,0).Vector() *
                ((HexRadius-1.)*RootThree/2.) + FVector(0,0,.45);
            Grid->AddInstance(FTransform(FRotator(0,Angle+90.,0),Mid,
                FVector((HexRadius-1.)/100.,.013,.006)));
        }
    }
    for (int32 I=0; I<9; ++I)
    {
        const double Y = -256.+64*I;
        Piece(Cube,{-312,Y,.5},{78,54,1},FLinearColor(.015f,.02f,.025f),false);
        if (I) Piece(Cube,{-315,Y-32,10},{69,4,20},Edge);
    }
    if (!GetWorld()->IsGameWorld() || !GetWorld()->GetMapName().EndsWith(TEXT("BumpitCell"))) BuildRoom();
    Ball = Piece(Sphere,LaunchPosition,FVector(2.*BallRadius),FLinearColor(.95f,.96f,.99f));
    Ball->SetCollisionProfileName(TEXT("PhysicsActor"));
    Ball->SetNotifyRigidBodyCollision(true);
    Ball->BodyInstance.bUseCCD = true;
    Ball->OnComponentHit.AddDynamic(this,&APinballTable::OnBallHit);
}

void APinballTable::SetObstacle(int32 Index,int32 Type)
{
    auto& Part = Obstacles[Index];
    if (Part) { Part->DestroyComponent(); Part = nullptr; }
    if (!Type) return;
    const FVector Position = HexCenter(Index) + FVector(0,0,15);
    Part = Type == 1 ? Piece(Cylinder,Position,{30,30,30},Aqua)
        : Piece(Cube,Position,{12,63,30},Type == 2 ? Amber : Rose,true,Type == 2 ? -33 : 33);
    Part->ComponentTags.Add(TEXT("Bumper"));
    if (Type == 1) Part->ComponentTags.Add(TEXT("RoundBumper"));
}

int32 APinballTable::PickCell(const FVector& Origin,const FVector& Direction) const
{
    const auto Transform = GetActorTransform();
    const FVector Start = Transform.InverseTransformPosition(Origin);
    const FVector Ray = Transform.InverseTransformVectorNoScale(Direction);
    if (Ray.Z >= -KINDA_SMALL_NUMBER) return INDEX_NONE;
    const double Distance = -Start.Z/Ray.Z;
    if (Distance < 0) return INDEX_NONE;
    const FVector P = Start + Ray*Distance;
    for (int32 Index=0; Index<Obstacles.Num(); ++Index)
    {
        const FVector Offset = (P-HexCenter(Index)).GetAbs();
        if (Offset.Y <= RootThree*HexRadius/2. && Offset.X + Offset.Y/RootThree <= HexRadius)
            return Index;
    }
    return INDEX_NONE;
}

FVector APinballTable::GoalLabel(int32 Lane) const
{
    return GetActorTransform().TransformPosition({-315,-256.+64*Lane,4});
}

void APinballTable::ResetBall()
{
    StopBall();
    SetLaunchGateClosed(false);
    Ball->AttachToComponent(RootComponent,FAttachmentTransformRules::KeepWorldTransform);
    Ball->SetRelativeLocation(LaunchPosition,false,nullptr,ETeleportType::TeleportPhysics);
}

void APinballTable::Launch(float Power)
{
    ResetBall();
    Hits = 0;
    Ball->SetSimulatePhysics(true);
    IncomingVelocity = GetActorTransform().TransformVectorNoScale({780.+400*Power,0,0});
    Ball->SetPhysicsLinearVelocity(IncomingVelocity);
    SetActorTickEnabled(true);
}

void APinballTable::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if (!LaunchGate->IsCollisionEnabled())
    {
        const double BallY = GetActorTransform().InverseTransformPosition(Ball->GetComponentLocation()).Y;
        if (BallY < DividerY - DividerThickness/2 - BallRadius)
            SetLaunchGateClosed(true);
    }
    IncomingVelocity = Ball->GetPhysicsLinearVelocity();
}

void APinballTable::SetLaunchGateClosed(bool Closed)
{
    LaunchGate->SetVisibility(Closed);
    LaunchGate->SetCollisionEnabled(Closed ? ECollisionEnabled::QueryAndPhysics : ECollisionEnabled::NoCollision);
}

int32 APinballTable::CheckBall() const
{
    const FVector P = GetActorTransform().InverseTransformPosition(Ball->GetComponentLocation());
    if (P.Z < -50 || P.Y < -310 || P.Y > 389) return -2;
    if (P.X <= -310 && P.Y < Width/2) return FMath::Clamp(FMath::FloorToInt((P.Y+Width/2)/(Width/9)),0,8);
    return -1;
}

void APinballTable::StopBall()
{
    SetActorTickEnabled(false);
    Ball->SetSimulatePhysics(false);
}

void APinballTable::OnBallHit(UPrimitiveComponent*,AActor*,UPrimitiveComponent* Other,FVector Impulse,const FHitResult& Hit)
{
    if (!Other || !Other->ComponentHasTag(TEXT("Bumper"))) return;
    if (Impulse.Size() > Ball->GetMass()*35) ++Hits;
    if (!Other->ComponentHasTag(TEXT("RoundBumper")) || !Ball->IsSimulatingPhysics()) return;

    const FVector Up = GetActorUpVector();
    if (FMath::Abs(FVector::DotProduct(Hit.ImpactNormal, Up)) > .75) return;
    const FVector Radial = FVector::VectorPlaneProject(Hit.ImpactPoint - Other->GetComponentLocation(), Up).GetSafeNormal();
    const FVector Approach = FVector::VectorPlaneProject(IncomingVelocity, Up);
    if (FVector::DotProduct(Approach, Radial) >= -KINDA_SMALL_NUMBER) return;

    // Mirror the incoming path on the circular rim, independently of the mesh's convex facets.
    const FVector Reflected = Approach.MirrorByVector(Radial).GetSafeNormal();
    constexpr double MinimumKickSpeed = 450.; // cm/s along the playfield
    const FVector Kick = Reflected * FMath::Max(Approach.Size(), MinimumKickSpeed);
    const FVector Outgoing = Kick + Up * FVector::DotProduct(Ball->GetPhysicsLinearVelocity(), Up);
    Ball->SetPhysicsLinearVelocity(Outgoing);
    IncomingVelocity = Outgoing;
}

void APinballTable::BuildRoom()
{
    // Furniture is level in world space while the playfield is pitched.
    const FLinearColor Iron(.075f,.085f,.082f), Rust(.28f,.115f,.056f), Wood(.21f,.135f,.073f);
    const FLinearColor Screen(.09f,.65f,.46f), Dark(.02f,.027f,.031f);
    const auto Box = [&](FVector P,FVector Size,FLinearColor Tint)
    {
        auto* Part = Piece(Cube,GetActorTransform().InverseTransformPosition(P),Size,Tint,false);
        Part->SetWorldRotation(FRotator::ZeroRotator);
        Part->ComponentTags.Add(TEXT("Room"));
        return Part;
    };
    Box({-310,0,-247},{1690,1680,24},Iron);
    Box({527,0,125},{16,1680,744},Rust);
    Box({-1147,0,125},{16,1680,744},Rust);
    for (int Side : {-1,1})
    {
        Box({-310,Side*836.,125},{1690,16,744},Iron);
        for(int I=0; I<7; ++I)
            Box({-1050.+I*245,Side*823.,120},{13,16,727},Rust);
        for(int I=0; I<6; ++I)
            Box({Side>0 ? 516. : -1136.,-742.+I*287,120},{17,15,727},Iron);
    }
    // Machine housing, adjacent settlement terminal, and barred service door.
    Box({0,0,-165},{652,570,143},Dark);
    Box({403,0,185},{66,611,146},Iron);
    Box({365,0,197},{8,508,63},Screen);
    Box({300,-530,-36},{161,185,400},Dark);
    Box({215,-530,39},{13,141,105},Iron);
    Box({206,-530,40},{6,119,70},Screen);
    Box({193,-530,-68},{45,142,18},Rust);
    for(int I=0; I<3; ++I)
        Box({168,-559.+I*30,-63},{12,17,7},Screen);
    Box({-580,824,-23},{280,14,420},Rust);
    for(int I=0; I<6; ++I)
        Box({-685.+I*41,811,62},{8,12,170},Iron);
    // A grated floor hatch separates the two working sides of the cell.
    Box({-639,0,-232},{301,349,6},Dark);
    for(int I=0; I<13; ++I)
        Box({-639,-161.+I*27,-224},{296,7,9},Rust);
    // Counter with physical stock samples, a wall rack, and drawer pulls.
    Box({-1048,50,-132},{135,635,208},Wood);
    Box({-1048,50,-19},{159,661,19},Iron);
    for(int I=0; I<3; ++I)
    {
        const double Y=-151.+I*200;
        Box({-971,Y,-126},{10,175,71},Rust);
        Box({-963,Y,-113},{10,64,9},Iron);
        auto* Sample = Piece(I==0 ? Cylinder.Get() : Cube.Get(),
            GetActorTransform().InverseTransformPosition({-1045,Y,14}),
            I==0 ? FVector(68,68,46) : FVector(22,94,46),I==0 ? Aqua : I==1 ? Amber : Rose,false);
        Sample->ComponentTags.Add(TEXT("Room"));
        Sample->SetWorldRotation(FRotator(0,I==1 ? -33 : 33,0));
    }
    Box({-1120,50,119},{30,650,16},Wood);
    Box({-1120,50,235},{30,650,16},Wood);
}
