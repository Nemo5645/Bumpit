#include "BumpitBoard.h"
#include "PinballTable.h"
#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "Engine/DirectionalLight.h"
#include "Engine/PointLight.h"
#include "Components/PointLightComponent.h"
#include "Components/LightComponent.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "GameFramework/PlayerController.h"
#include "InputCoreTypes.h"

namespace
{
const FLinearColor Ink(.012f,.022f,.037f), Panel(.032f,.055f,.080f), Grid(.065f,.105f,.145f);
const FLinearColor White(.9f,.94f,.96f), Muted(.49f,.62f,.68f);
const FLinearColor Mint(.20f,.94f,.69f), Gold(1,.66f,.19f), Coral(.98f,.37f,.30f);
const FLinearColor Colors[] = {Mint, Gold, Coral};
const TCHAR* Names[] = {TEXT("라운드 범퍼"), TEXT("왼쪽 경사판"), TEXT("오른쪽 경사판")};
constexpr int32 Prices[] = {3,4,4};
constexpr int32 Multipliers[] = {1,2,5,2,10,2,5,2,1};
bool Inside(FVector2D P, double X, double Y, double W, double H)
{
    return P.X >= X && P.X < X+W && P.Y >= Y && P.Y < Y+H;
}
}

ABumpitGameMode::ABumpitGameMode()
{
    HUDClass = ABumpitBoard::StaticClass();
    DefaultPawnClass = nullptr;
}

void ABumpitBoard::BeginPlay()
{
    Super::BeginPlay();
    auto* PC = GetOwningPlayerController();
    Table = GetWorld()->SpawnActor<APinballTable>(FVector::ZeroVector,FRotator(18,0,0));
    const FRotator View(-56,0,0);
    const FVector Focus(0,188,0);
    ViewCamera = GetWorld()->SpawnActor<ACameraActor>(Focus-View.Vector()*1280,View);
    auto* Lens = ViewCamera->GetCameraComponent();
    Lens->FieldOfView = 53;
    Lens->AspectRatio = 1200.f/740.f;
    Lens->bConstrainAspectRatio = true;
    Lens->PostProcessSettings.bOverride_AutoExposureMinBrightness = true;
    Lens->PostProcessSettings.bOverride_AutoExposureMaxBrightness = true;
    Lens->PostProcessSettings.AutoExposureMinBrightness = 1;
    Lens->PostProcessSettings.AutoExposureMaxBrightness = 1;
    PC->bAutoManageActiveCameraTarget = false;
    PC->SetViewTarget(ViewCamera);
    Visit(EStation::Room);
    UpdateCamera(1.f);
    auto* KeyLight = GetWorld()->SpawnActor<ADirectionalLight>(FVector(0,0,600),FRotator(-58,-40,0));
    KeyLight->GetLightComponent()->SetMobility(EComponentMobility::Movable);
    KeyLight->GetLightComponent()->SetIntensity(2.2f);
    for (const FVector& Position : {FVector(100,-380,365),FVector(-783,20,275)})
    {
        auto* Light = GetWorld()->SpawnActor<APointLight>(Position,FRotator::ZeroRotator);
        auto* Lamp = CastChecked<UPointLightComponent>(Light->GetLightComponent());
        Lamp->SetMobility(EComponentMobility::Movable);
        Lamp->SetIntensity(2600.f);
        Lamp->SetAttenuationRadius(1350.f);
        Lamp->SetLightColor(FLinearColor(1.f,.78f,.52f));
    }
    PC->bShowMouseCursor = true;
    FInputModeGameAndUI Input;
    Input.SetHideCursorDuringCapture(false);
    PC->SetInputMode(Input);
    Message = TEXT("상점에서 첫 장애물을 구매하세요.");
    UE_LOG(LogTemp, Display, TEXT("BUMPIT board ready"));
}

void ABumpitBoard::Visit(EStation NewStation)
{
    if (Looking) SetLooking(false);
    Station = NewStation;
    Charging = false;
    FVector Eye, Target;
    switch (Station)
    {
    case EStation::Room: Eye={-925,-555,160}; Target={155,5,5}; break;
    case EStation::Shop: Eye={-537,75,111}; Target={-1048,50,0}; break;
    case EStation::Terminal: Eye={-88,-526,66}; Target={240,-530,-5}; break;
    default: Target={0,100,0}; Eye=Target-FRotator(-56,0,0).Vector()*1330; break;
    }
    MoveCamera(Eye,Target,Station == EStation::Room ? 78.f : 53.f);
}

void ABumpitBoard::MoveCamera(FVector Eye, FVector Target, float Fov)
{
    ViewPivot = Target;
    BlendFrom = ViewCamera->GetActorTransform();
    BlendTo = FTransform((Target-Eye).Rotation(),Eye);
    FromFov = ViewCamera->GetCameraComponent()->FieldOfView;
    ToFov = Fov;
    BlendTime = 0;
    Blending = true;
}

void ABumpitBoard::UpdateCamera(float DeltaSeconds)
{
    if (!Blending) return;
    BlendTime = FMath::Min(1.f, BlendTime + DeltaSeconds/.55f);
    FTransform Pose;
    const float T = FMath::SmoothStep(0.f,1.f,BlendTime);
    Pose.Blend(BlendFrom,BlendTo,T);
    ViewCamera->SetActorTransform(Pose);
    ViewCamera->GetCameraComponent()->SetFieldOfView(FMath::Lerp(FromFov,ToFov,T));
    Blending = BlendTime < 1.f;
}

void ABumpitBoard::FocusView(const FVector& Eye, const FVector& Direction)
{
    if (Looking) SetLooking(false);
    if (Station == EStation::Room)
    {
        const FBox Stations[] = { FBox(FVector(-352,-300,-230),FVector(440,385,260)),
            FBox(FVector(-1140,-285,-233),FVector(-955,385,245)), FBox(FVector(166,-627,-235),FVector(385,-432,170)) };
        float Nearest = 1.f;
        int32 Pick = INDEX_NONE;
        for (int32 I=0; I<UE_ARRAY_COUNT(Stations); ++I)
        {
            FVector Hit, Normal;
            float Time;
            if (FMath::LineExtentBoxIntersection(Stations[I],Eye,Eye+Direction*4000,FVector::ZeroVector,Hit,Normal,Time)
                && Time < Nearest) { Nearest = Time; Pick = I; }
        }
        if (Pick != INDEX_NONE) { Visit(static_cast<EStation>(Pick+1)); return; }
    }
    if (Station == EStation::Table && Table->PickCell(Eye,Direction) != INDEX_NONE)
    {
        const FVector Target = FMath::RayPlaneIntersection(Eye,Direction,FPlane(Table->GetActorLocation(),Table->GetActorUpVector()));
        MoveCamera(Target - Direction*800,Target,48.f);
        return;
    }
    const FVector CameraEye = ViewCamera->GetActorLocation();
    MoveCamera(CameraEye,CameraEye+Direction*600,Station==EStation::Room ? 52.f : 40.f);
}

void ABumpitBoard::SetLooking(bool Enabled)
{
    Looking = Enabled;
    auto* PC = GetOwningPlayerController();
    PC->bShowMouseCursor = !Enabled;
    if (Enabled)
    {
        Charging = false;
        PC->SetInputMode(FInputModeGameOnly());
    }
    else
    {
        FInputModeGameAndUI Input;
        Input.SetHideCursorDuringCapture(false);
        PC->SetInputMode(Input);
    }
}

void ABumpitBoard::RotateView(float MouseX, float MouseY)
{
    FRotator Rotation = ViewCamera->GetActorRotation();
    Rotation.Yaw += MouseX * .24f;
    const bool Orbit = Station == EStation::Table;
    Rotation.Pitch = FMath::Clamp(Rotation.Pitch + MouseY * .24f, Orbit ? -84. : -80., Orbit ? -40. : 80.);
    FVector Eye = ViewCamera->GetActorLocation();
    if (Orbit) Eye = ViewPivot - Rotation.Vector() * FVector::Distance(Eye, ViewPivot);
    ViewCamera->SetActorLocationAndRotation(Eye, Rotation);
}

void ABumpitBoard::Walk(FVector2D Input, float DeltaSeconds)
{
    if (Blending || Input.IsNearlyZero()) return;
    if (Station != EStation::Room)
    {
        const EStation Previous = Station;
        const FVector Landing = Previous == EStation::Table ? FVector(-532,0,160) :
            Previous == EStation::Shop ? FVector(-730,70,160) : FVector(-30,-530,160);
        const FVector Target = Previous == EStation::Table ? FVector(100,0,20) :
            Previous == EStation::Shop ? FVector(-1048,50,0) : FVector(240,-530,0);
        Station = EStation::Room;
        Charging = false;
        MoveCamera(Landing,Target,78.f);
        return;
    }
    const FRotator Heading(0,ViewCamera->GetActorRotation().Yaw,0);
    const FVector2D Axis = Input.GetSafeNormal();
    const FVector Step = Heading.RotateVector({Axis.X,Axis.Y,0}) * (420.*FMath::Min(DeltaSeconds,.1f));
    FVector Eye = ViewCamera->GetActorLocation();
    const auto Clear = [](const FVector& P)
    {
        // The inset wall and furniture footprints leave a shoulder-width clearance.
        return P.X > -1090 && P.X < 472 && FMath::Abs(P.Y) < 785 &&
            !(P.X > -396 && P.Y > -346 && P.Y < 420) &&
            !(P.X > 130 && P.X < 425 && P.Y > -665 && P.Y < -400) &&
            !(P.X < -925 && P.Y > -320 && P.Y < 418);
    };
    if (Clear(Eye+FVector(Step.X,0,0))) Eye.X += Step.X;
    if (Clear(Eye+FVector(0,Step.Y,0))) Eye.Y += Step.Y;
    ViewCamera->SetActorLocation(Eye);
}

void ABumpitBoard::Buy(int32 Type)
{
    if (Phase != EPhase::Build) return;
    if (Credits < Prices[Type]) { Message = TEXT("크레딧이 부족합니다."); return; }
    Credits -= Prices[Type];
    ++Stock[Type];
    Selected = Type;
    Message = TEXT("빈 칸을 클릭해 배치하세요.");
}

void ABumpitBoard::Edit(int32 Index, bool Remove)
{
    if (Phase != EPhase::Build) return;
    int32& Cell = Cells[Index];
    if (Cell)
    {
        Selected = Cell-1;
        ++Stock[Selected];
        Cell = 0;
        Table->SetObstacle(Index,Cell);
        Message = Remove ? TEXT("장애물을 보관함에 회수했습니다.") : TEXT("옮길 빈 칸을 클릭하세요.");
    }
    else if (!Remove && Stock[Selected] > 0)
    {
        --Stock[Selected];
        Cell = Selected+1;
        Table->SetObstacle(Index,Cell);
        Message = TEXT("배치 완료. 준비되면 발사하세요.");
    }
    else if (!Remove) Message = TEXT("선택한 장애물을 먼저 구매하세요.");
}

void ABumpitBoard::Advance()
{
    if (Phase == EPhase::Result)
    {
        ++Stage;
        Visit(EStation::Shop);
        Table->ResetBall();
        Phase = EPhase::Build;
        Message = TEXT("이전 배치를 유지했습니다. 다시 설계하세요.");
    }
    else if (Phase == EPhase::Build)
    {
        Table->Launch(Power);
        Charging = false;
        Hits = 0;
        Phase = EPhase::Flight;
        Message = TEXT("공이 이동하고 있습니다.");
    }
}

void ABumpitBoard::Settle(bool Scored)
{
    Table->StopBall();
    Hits = Table->Hits;
    Earned = Scored ? (100 + Hits*25)*Multipliers[Lane] : 0;
    Total += Earned;
    Credits += 4 + FMath::Min(Earned/150,8);
    Phase = EPhase::Result;
    Visit(EStation::Terminal);
    Message = Scored ? FString::Printf(TEXT("(%d + %d × 25) × %d = %d점"),100,Hits,Multipliers[Lane],Earned)
                     : TEXT("공이 보드 밖으로 나갔습니다 · 기본 지원금 지급");
}

void ABumpitBoard::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    auto* PC = GetOwningPlayerController();
    if (!PC) return;
    UpdateCamera(DeltaSeconds);
    bool CameraInput = Blending;
    if (!Blending && PC->WasInputKeyJustPressed(EKeys::R))
    {
        SetLooking(!Looking);
        CameraInput = true;
    }
    if (Looking)
    {
        float DX, DY;
        PC->GetInputMouseDelta(DX,DY);
        RotateView(DX,DY);
        if (PC->WasInputKeyJustPressed(EKeys::LeftMouseButton))
            FocusView(ViewCamera->GetActorLocation(),ViewCamera->GetActorForwardVector());
        CameraInput = true;
    }
    Walk({double(PC->IsInputKeyDown(EKeys::W))-PC->IsInputKeyDown(EKeys::S),
        double(PC->IsInputKeyDown(EKeys::D))-PC->IsInputKeyDown(EKeys::A)}, DeltaSeconds);
    CameraInput |= Blending;
    if (Phase == EPhase::Flight)
    {
        const int32 Catch = Table->CheckBall();
        if (Catch >= 0) { Lane = Catch; Settle(true); }
        else if (Catch == -2) Settle(false);
        return;
    }
    if (CameraInput) return;
    if (PC->WasInputKeyJustPressed(EKeys::Tab)) Visit(EStation::Room);
    if (PC->WasInputKeyJustPressed(EKeys::One)) Visit(EStation::Table);
    if (PC->WasInputKeyJustPressed(EKeys::Two)) Visit(EStation::Shop);
    if (PC->WasInputKeyJustPressed(EKeys::Three)) Visit(EStation::Terminal);
    if (Station == EStation::Terminal && Phase == EPhase::Result && PC->WasInputKeyJustPressed(EKeys::SpaceBar))
    { Advance(); return; }
    if (Station == EStation::Table && Phase == EPhase::Build)
    {
        if (PC->WasInputKeyJustPressed(EKeys::SpaceBar)) { Charging = true; Power = 0; }
        if (Charging) Power = FMath::Min(1.f, Power + DeltaSeconds/1.4f);
        if (Charging && PC->WasInputKeyJustReleased(EKeys::SpaceBar)) { Advance(); return; }
    }
    float X,Y;
    if (!PC->GetMousePosition(X,Y)) return;
    Pointer = (FVector2D(X,Y)-Origin)/Scale;
    const bool Click = PC->WasInputKeyJustPressed(EKeys::LeftMouseButton);
    const bool Remove = PC->WasInputKeyJustPressed(EKeys::RightMouseButton);
    if (Station == EStation::Room && Click)
    {
        FVector Eye, Direction;
        if (PC->DeprojectMousePositionToWorld(Eye,Direction)) FocusView(Eye,Direction);
        return;
    }
    if (Click && Station==EStation::Terminal && Phase==EPhase::Result && Inside(Pointer,750,605,380,58))
    { Advance(); return; }
    if (Phase != EPhase::Build || (!Click && !Remove)) return;
    for (int32 I=0; I<3; ++I)
    {
        if (Station==EStation::Shop && Click && Inside(Pointer,750,233+I*82,380,70))
        {
            if (Pointer.X >= 1010) Buy(I);
            else { Selected = I; Message = TEXT("선택한 종류를 빈 칸에 배치하세요."); }
            return;
        }
    }
    if (Station != EStation::Table) return;
    FVector RayStart, RayDirection;
    if (PC->DeprojectMousePositionToWorld(RayStart,RayDirection))
    {
        const int32 Index = Table->PickCell(RayStart,RayDirection);
        if (Index != INDEX_NONE) Edit(Index,Remove);
    }
}

void ABumpitBoard::Rect(float X,float Y,float W,float H,FLinearColor Color)
{
    DrawRect(Color,Origin.X+X*Scale,Origin.Y+Y*Scale,W*Scale,H*Scale);
}
void ABumpitBoard::Label(const FString& Text,float X,float Y,float Size,FLinearColor Color)
{
    DrawText(Text,Color,Origin.X+X*Scale,Origin.Y+Y*Scale,GEngine->GetMediumFont(),Size*Scale);
}
void ABumpitBoard::DrawHUD()
{
    Super::DrawHUD();
    if (!Canvas || Canvas->ClipX <= 0 || Canvas->ClipY <= 0) return;
    Scale = FMath::Min(Canvas->ClipX/1200.f,Canvas->ClipY/740.f);
    Origin = FVector2D((Canvas->ClipX-1200*Scale)/2,(Canvas->ClipY-740*Scale)/2);
    Rect(32,82,428,30,Ink);
    Label(Looking ? TEXT("마우스로 둘러보기   ·   좌클릭으로 가까이 보기") :
        TEXT("WASD  이동   ·   R  둘러보기   ·   TAB  방 전경"),43,85,.95f,Looking ? Mint : Muted);
    if (Looking)
    {
        Rect(593,369,14,2,White);
        Rect(599,363,2,14,White);
    }
    if (Station == EStation::Room)
    {
        Rect(50,607,675,85,Ink);
        Label(TEXT("작업실   /   정면 핀볼 기계 · 왼쪽 정산 단말기"),68,617,1.15f,White);
        Label(TEXT("기계를 클릭해 가까이 보세요. 맞은편 상점은 R로 둘러보세요."),68,655,.96f,Mint);
        return;
    }
    if (Station == EStation::Terminal)
    {
        Rect(734,371,421,311,Ink);
        Label(FString::Printf(TEXT("SETTLEMENT  /  %02d"),Stage),750,392,1.8f,Mint);
        Label(FString::Printf(TEXT("누적 점수  %lld     크레딧  %d"),Total,Credits),750,457,1.1f,Gold);
        Label(Phase==EPhase::Result ? Message : TEXT("발사 후 이곳에서 정산합니다."),750,532,1.f,White);
        if (Phase==EPhase::Result)
        {
            Rect(750,605,380,58,Mint);
            Label(TEXT("다음 스테이지  [SPACE]"),766,617,1.1f,Ink);
        }
        return;
    }
    if (Station == EStation::Table)
    {
        for (int32 I=0; I<9; ++I)
        {
            FVector2D Screen;
            if (GetOwningPlayerController()->ProjectWorldLocationToScreen(Table->GoalLabel(I),Screen))
                DrawText(FString::Printf(TEXT("×%d"),Multipliers[I]),White,Screen.X-11*Scale,Screen.Y-9*Scale,
                    GEngine->GetMediumFont(),1.02f*Scale);
        }
        Rect(886,115,295,166,Ink);
        Label(TEXT("LAUNCH CONTROL"),901,131,1.22f,Mint);
        Label(TEXT("Space를 누르고 떼면 발사"),901,175,1.f,White);
        Rect(902,221,252,11,Grid);
        Rect(902,221,252*Power,11,Gold);
        Label(Phase==EPhase::Flight ? TEXT("공 이동 중") : Names[Selected],901,244,.94f,Muted);
        Rect(32,690,1136,40,Ink);
        Label(Message,49,697,.94f,White);
        Label(TEXT("좌클릭 배치 / 이동   ·   우클릭 회수"),745,697,.93f,Muted);
        return;
    }
    Rect(732,103,421,560,Ink);
    Label(TEXT("WORKSHOP"),750,131,1.8f,White);
    Label(FString::Printf(TEXT("보유 크레딧  %d"),Credits),750,188,1.08f,Gold);
    for (int32 I=0; I<3; ++I)
    {
        const float Y=233+82*I;
        Rect(750,Y,380,70,Panel); Rect(750,Y,5,70,Selected==I ? Colors[I] : Grid);
        Label(Names[I],768,Y+7,1.13f,White);
        Label(FString::Printf(TEXT("보관함  %d"),Stock[I]),768,Y+39,.82f,Muted);
        Rect(1010,Y+10,109,50,Grid);
        Label(FString::Printf(TEXT("구매  %d"),Prices[I]),1027,Y+19,1.0f,Gold);
    }
    Label(Message,750,513,.99f,White);
    Label(TEXT("구매 후  [1] 핀볼로 이동"),750,581,1.1f,Mint);
}
