"""Run from the UE Python console with BumpitCell open and PIE stopped."""
import math
import time
import unreal

MAP = "/Game/Bumpit/Maps/BumpitCell"
ASSETS = "/Game/Bumpit/Blueprints/"
EDITOR = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
LEVEL = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)


def blueprint_class(name):
    return unreal.load_class(None, f"{ASSETS}{name}.{name}_C")


def check(value, message):
    if not value:
        raise AssertionError(message)


class BumpitPlaytest:
    def start(self):
        check(EDITOR.get_game_world() is None, "Stop PIE before starting the test")
        check(EDITOR.get_editor_world().get_path_name().startswith(MAP + "."), "Open BumpitCell")
        self.phase = "initialize"
        self.deadline = time.monotonic() + 45
        self.hud_class = blueprint_class("BP_BumpitHUD")
        self.table_class = blueprint_class("BP_PinballTable")
        self.handle = unreal.register_slate_post_tick_callback(self.tick)
        LEVEL.editor_request_begin_play()

    def finish(self, passed, message):
        unreal.unregister_slate_post_tick_callback(self.handle)
        LEVEL.editor_request_end_play()
        logger = unreal.log if passed else unreal.log_error
        logger(f"Bumpit Blueprint playtest {'PASS' if passed else 'FAIL'}: {message}")

    def setup_round(self, hud):
        get = hud.get_editor_property
        table = get("Table")
        camera = get("ViewCamera")
        check(table and camera and get("Credits") == 12 and get("Stage") == 1, "Initial board state")
        entrance = camera.get_actor_location()
        hud.call_method("Walk", (1.0, 0.0, 0.1))
        check((camera.get_actor_location() - entrance).length() > 40, "Room camera movement")
        eye = camera.get_actor_location()
        hud.call_method("Focus", (eye, -eye / eye.length()))
        check(get("Station") == 1 and get("Blending"), f"Table focus: eye={eye}, station={get('Station')}, blending={get('Blending')}, hit={hud.call_method('BoxDistance', (eye, -eye / eye.length(), unreal.Vector(-352,-300,-230), unreal.Vector(440,385,260)))}")
        hud.call_method("UpdateView", (0.25,))
        check(get("Blending") and (camera.get_actor_location() - eye).length() > 0.01, "Camera blend")
        hud.call_method("UpdateView", (1.0,))
        transform = table.get_actor_transform()
        aim = unreal.MathLibrary.transform_location(transform, unreal.Vector(146.25, -253.3124, 0))
        eye = camera.get_actor_location()
        direction = (aim - eye) / (aim - eye).length()
        check(table.call_method("PickCell", (eye, direction)) == 0, "Angled hex picking")
        hud.call_method("Focus", (eye, direction))
        hud.call_method("UpdateView", (1.0,))
        check((camera.get_actor_location() - aim).length() < (eye - aim).length(), "Cell zoom")
        notch = unreal.MathLibrary.transform_location(transform, unreal.Vector(185, -224, 100))
        check(table.call_method("PickCell", (notch, -table.get_actor_up_vector())) == -1, "Hex corner")
        for index, multiplier in enumerate([1, 2, 5, 2, 10, 2, 5, 2, 1]):
            check(hud.call_method("LaneMultiplier", (index,)) == multiplier, f"Lane {index}")
        hud.call_method("Purchase", (0,))
        check(get("Credits") == 9 and get("Stock")[0] == 1, "Purchase")
        hud.call_method("EditCell", (3, False))
        hud.call_method("EditCell", (3, True))
        check(get("CellTypes")[3] == 0 and get("Stock")[0] == 1, "Recover bumper")
        hud.call_method("EditCell", (4, False))
        hud.call_method("StartRound")
        check(get("Phase") == 1, "Launch")
        hud.call_method("UpdateBoard", (25.0,))
        check(get("Phase") == 1, "Flight must end through physical contact, not elapsed time")

    def finish_round(self, hud):
        get = hud.get_editor_property
        points = get("LastPoints")
        check(points > 0 and get("TotalPoints") == points, "Score")
        check(get("Credits") == 9 + min(points // 150, 8) + 4, "Credit reward")
        gate = get("Table").get_editor_property("LaunchGate")
        check(gate.is_collision_enabled(), "Closed launch gate")
        hud.call_method("NextStage")
        check(get("Stage") == 2 and get("Phase") == 0 and get("CellTypes")[4] == 1, "Next stage")
        check(not gate.is_collision_enabled(), "Gate reset")
        self.points = points

    def start_reflection(self, world):
        # A separate, level rig isolates reflection from slope and other obstacles.
        transform = unreal.Transform(location=unreal.Vector(3000, 0, 5000))
        gameplay = unreal.get_default_object(unreal.GameplayStatics)
        scale = unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT
        actor = gameplay.call_method("BeginDeferredActorSpawnFromClass", (
            world, self.table_class, transform,
            unreal.SpawnActorCollisionHandlingMethod.ALWAYS_SPAWN, None, scale,
        ))
        self.rig = gameplay.call_method("FinishSpawningActor", (actor, transform, scale))
        self.rig.call_method("SetObstacle", (19, 1))
        self.rig.call_method("Launch", (0.0,))
        self.ball = self.rig.get_editor_property("Ball")
        center = self.rig.call_method("HexCenter", (19,)) + unreal.Vector(3000, 0, 5015)
        self.ball.set_world_location(center + unreal.Vector(-70, 12, 0), False, True)
        self.ball.set_enable_gravity(False)
        self.ball.set_physics_linear_velocity(unreal.Vector(280, 0, 0))

    def tick(self, delta):
        try:
            check(time.monotonic() < self.deadline, f"Timeout during {self.phase}")
            world = EDITOR.get_game_world()
            if not world:
                return
            if self.phase == "initialize":
                actors = unreal.GameplayStatics.get_all_actors_of_class(world, self.hud_class)
                if not actors:
                    return
                self.hud = actors[0]
                self.setup_round(self.hud)
                self.phase = "flight"
            elif self.phase == "flight" and self.hud.get_editor_property("Phase") == 2:
                self.finish_round(self.hud)
                self.start_reflection(world)
                self.phase = "reflection"
            elif self.phase == "reflection" and self.rig.call_method("HitCount") > 0:
                velocity = self.ball.get_physics_linear_velocity()
                speed = math.hypot(velocity.x, velocity.y)
                alignment = (-0.5 * velocity.x + math.sqrt(0.75) * velocity.y) / max(speed, 1)
                check(speed >= 440 and alignment > math.cos(math.radians(10)), "Round bumper reflection")
                self.finish(True, f"score={self.points}, stage=2, reflected speed={speed:.1f}")
        except Exception as error:
            self.finish(False, repr(error))


BumpitPlaytest().start()

