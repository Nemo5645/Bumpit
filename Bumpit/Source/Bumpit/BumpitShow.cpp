#include "BumpitShow.h"
#include "CanvasItem.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/Canvas.h"
#include "Engine/CanvasRenderTarget2D.h"
#include "Engine/Font.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
// The screen hangs above the BUMPIT sign, in front of the back wall.
const FVector ScreenLocation(431,0,380), FrameLocation(476,0,380);
const FVector ScreenScale(5.6,1.7,1), FrameScale(.88,5.9,1.95);
// The plane's X runs along the text and its Y down the lines, so it reads upright from the room.
const FVector ScreenTextAxis(0,1,0), ScreenDownAxis(0,0,-1);
constexpr int32 ImageWidth = 576, ImageHeight = 176;
constexpr float LineHeight = 56, TextScale = 3, BannerScale = 6;
const FLinearColor ScreenColor(.42f,.03f,.02f), PassColor(.03f,.30f,.07f), ScreenTextColor(1,.86f,.62f), ReachedColor(1,.72f,.12f);

// Coins leave the cabinet under the table, spread out, and settle on the floor.
const FVector CoinMouth(-340,0,-140), CoinSize(.16,.16,.035);
constexpr float PourLength = 2.2f, CoinGravity = -980, FloorZ = -232, CoinBounce = .35f;
constexpr float MouthHalfWidth = 170;
const FLinearColor CoinColor(.95f,.62f,.1f,1), FrameColor(.03f,.025f,.02f,1);
constexpr float CoinGlow = .9f;

UMaterialInstanceDynamic* MoodMaterial(UObject* Outer, const FLinearColor& Color, float Glow)
{
    UMaterialInterface* Mood = LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Bumpit/Mood/M_BumpitMood.M_BumpitMood"));
    UMaterialInstanceDynamic* Material = UMaterialInstanceDynamic::Create(Mood,Outer);
    if (Material)
    {
        Material->SetVectorParameterValue(TEXT("Color"),Color);
        Material->SetScalarParameterValue(TEXT("Glow"),Glow);
    }
    return Material;
}
}

ABumpitShow::ABumpitShow()
{
    PrimaryActorTick.bCanEverTick = true;
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Cube(TEXT("/Engine/BasicShapes/Cube.Cube"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Plane(TEXT("/Engine/BasicShapes/Plane.Plane"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Cylinder(TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
    RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
    Frame = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Frame"));
    Screen = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Screen"));
    Coins = CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("Coins"));
    for (USceneComponent* Part : TArray<USceneComponent*>{Frame,Screen,Coins}) Part->SetupAttachment(RootComponent);
    Frame->SetStaticMesh(Cube.Object);
    Frame->SetRelativeLocation(FrameLocation);
    Frame->SetRelativeScale3D(FrameScale);
    Frame->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Screen->SetStaticMesh(Plane.Object);
    Screen->SetRelativeLocationAndRotation(ScreenLocation,FRotationMatrix::MakeFromXY(ScreenTextAxis,ScreenDownAxis).Rotator());
    Screen->SetRelativeScale3D(ScreenScale);
    Screen->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Screen->SetCastShadow(false);
    Coins->SetStaticMesh(Cylinder.Object);
    Coins->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Coins->SetCastShadow(false);
}

void ABumpitShow::BeginPlay()
{
    Super::BeginPlay();
    Frame->SetMaterial(0,MoodMaterial(this,FrameColor,0));
    Coins->SetMaterial(0,MoodMaterial(this,CoinColor,CoinGlow));
    ScreenImage = Cast<UCanvasRenderTarget2D>(UCanvasRenderTarget2D::CreateCanvasRenderTarget2D(
        this,UCanvasRenderTarget2D::StaticClass(),ImageWidth,ImageHeight));
    UMaterialInterface* Base = LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Bumpit/Mood/M_BumpitScreen.M_BumpitScreen"));
    if (!ScreenImage || !Base) return;
    ScreenImage->ClearColor = ScreenColor;
    ScreenImage->OnCanvasRenderTargetUpdate.AddDynamic(this,&ABumpitShow::DrawScreen);
    UMaterialInstanceDynamic* Material = UMaterialInstanceDynamic::Create(Base,this);
    Material->SetTextureParameterValue(TEXT("Image"),ScreenImage);
    Screen->SetMaterial(0,Material);
    ScreenImage->UpdateResource();
}

void ABumpitShow::ShowScore(int32 BallPoints, int32 Target, int32 RoundPoints)
{
    ShownBall = BallPoints;
    ShownTarget = Target;
    ShownRound = RoundPoints;
    Banner.Reset();
    if (ScreenImage) ScreenImage->UpdateResource();
}

void ABumpitShow::ShowBanner(const FString& Text, bool bGreen)
{
    Banner = Text;
    bBannerGreen = bGreen;
    if (ScreenImage) ScreenImage->UpdateResource();
}

void ABumpitShow::DrawScreen(UCanvas* Canvas, int32 Width, int32 Height)
{
    const UFont* Font = LoadObject<UFont>(nullptr,TEXT("/Game/Bumpit/UI/F_Galmuri.F_Galmuri"));
    FCanvasTileItem Background(FVector2D::ZeroVector,FVector2D(Width,Height),
        !Banner.IsEmpty() && bBannerGreen ? PassColor : ScreenColor);
    Canvas->DrawItem(Background);
    const auto Write = [&](const FString& Text, float OffsetY, float Scale, const FLinearColor& Color)
    {
        FCanvasTextItem Label(FVector2D::ZeroVector,FText::FromString(Text),Font,Color);
        Label.Scale = FVector2D(Scale);
        Label.bCentreX = true;
        Label.bCentreY = true;
        Canvas->DrawItem(Label,FVector2D(Width/2.,Height/2.+OffsetY));
    };
    if (!Banner.IsEmpty())
    {
        Write(Banner,0,BannerScale,ScreenTextColor);
        return;
    }
    const auto Line = [&](int32 Row, const FString& Text, const FLinearColor& Color)
    {
        Write(Text,(Row-1)*LineHeight,TextScale,Color);
    };
    Line(0,FString::Printf(TEXT("점수  +%d"),ShownBall),ScreenTextColor);
    Line(1,FString::Printf(TEXT("목표  %d"),ShownTarget),ScreenTextColor);
    Line(2,FString::Printf(TEXT("총점  %d"),ShownRound),ShownRound >= ShownTarget ? ReachedColor : ScreenTextColor);
}

void ABumpitShow::PourCoins(int32 Count)
{
    ClearCoins();
    if (Count <= 0) return;
    Pour.SetNum(Count);
    PourTransforms.SetNum(Count);
    for (int32 Index=0; Index<Count; ++Index)
    {
        FCoin& Coin = Pour[Index];
        Coin.Position = CoinMouth+FVector(0,FMath::FRandRange(-MouthHalfWidth,MouthHalfWidth),FMath::FRandRange(-20.f,20.f));
        Coin.Velocity = FVector(FMath::FRandRange(-560.f,-160.f),FMath::FRandRange(-190.f,190.f),FMath::FRandRange(40.f,340.f));
        Coin.Rotation = FRotator(FMath::FRandRange(0.f,360.f),FMath::FRandRange(0.f,360.f),0);
        Coin.Spin = FRotator(FMath::FRandRange(300.f,900.f),FMath::FRandRange(-500.f,500.f),0);
        Coin.StartSeconds = PourLength*Index/Count;
        PourTransforms[Index] = FTransform(Coin.Rotation,Coin.Position,FVector::ZeroVector);
    }
    Coins->AddInstances(PourTransforms,false,true);
    PourSeconds = 0;
}

void ABumpitShow::ClearCoins()
{
    Pour.Reset();
    PourTransforms.Reset();
    Coins->ClearInstances();
}

void ABumpitShow::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime);
    if (Pour.IsEmpty()) return;
    PourSeconds += DeltaTime;
    for (int32 Index=0; Index<Pour.Num(); ++Index)
    {
        FCoin& Coin = Pour[Index];
        if (PourSeconds < Coin.StartSeconds) continue;
        Coin.Velocity.Z += CoinGravity*DeltaTime;
        Coin.Position += Coin.Velocity*DeltaTime;
        Coin.Rotation += Coin.Spin*DeltaTime;
        if (Coin.Position.Z < FloorZ)
        {
            Coin.Position.Z = FloorZ;
            Coin.Velocity *= FVector(.6,.6,-CoinBounce);
            Coin.Spin *= .5;
        }
        PourTransforms[Index] = FTransform(Coin.Rotation,Coin.Position,CoinSize);
    }
    Coins->BatchUpdateInstancesTransforms(0,PourTransforms,true,true);
}
