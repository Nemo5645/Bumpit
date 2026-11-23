"""Install the bumper audition in the existing game Blueprints using UE editor Python."""
import sys
import wave
from pathlib import Path

import unreal as u
from editor_toolset.toolsets.blueprint import ContainerType

sys.path.insert(0, str(Path(__file__).parent))
from render_bumper_notes import STARTS, DURATION
from blueprint_graph import B, Graph, HUD, ROOT, put

project = Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir()))
table = u.load_asset(ROOT + 'BP_PinballTable')
sound_dir = '/Game/Bumpit/Audio'
cells = (3, 8, 12, 16, 19, 23, 27, 31, 35, 38, 42)
array = '/Script/Engine.KismetArrayLibrary:'
game = '/Script/Engine.GameplayStatics:'

def import_notes():
    sounds = []
    with wave.open(str(project / 'AudioPreviews/bumper_chain_16.wav'), 'rb') as source:
        for index, start in enumerate(STARTS):
            path = project / 'Saved' / f'BumperHit{index + 1}.wav'
            source.setpos(start)
            with wave.open(str(path), 'wb') as clip:
                clip.setparams(source.getparams())
                clip.writeframes(source.readframes(round(DURATION * source.getframerate())))
            task = u.AssetImportTask()
            task.filename = str(path)
            task.destination_path = sound_dir
            task.automated = task.save = task.replace_existing = True
            u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
            sound = u.load_asset(sound_dir + '/' + path.stem)
            assert isinstance(sound, u.SoundWave)
            sound.set_editor_property('volume', 10 ** (4 / 20) if index == 0 else 1.35)
            assert u.EditorAssetLibrary.save_loaded_asset(sound, False)
            sounds.append(sound)
    return sounds

def after(g, node, function):
    outputs = B._get_node_info(node).output_pins
    dest = next(pin for pin in outputs if pin.name == 'then').connected_pins
    if any(B._get_node_info(pin.node).type_id == '|' + function for pin in dest):
        return
    g.tail = node.find_then_pin()
    g.tail.break_pin_links()
    g.action(function)
    for pin in dest:
        put(B._resolve_pin(pin), g.tail)

def variable(bp, name, kind, container=None):
    if name not in B.list_variables(bp):
        if container:
            B.add_object_variable(bp, name, kind.static_class(), container_type=container)
        else:
            B.add_variable(bp, name, kind)

sounds = import_notes()
variable(table, 'BumperNotes', u.SoundWave, ContainerType.ARRAY)
variable(table, 'BumperNoteIndex', 'int')
variable(table, 'LastBumperNoteTime', 'float')
B.compile_blueprint(table)
g = Graph(table, 'PlayBumperNote', True)
now = g.call(game + 'GetTimeSeconds').find_output_pin('ReturnValue')
elapsed = g.math('Subtract_DoubleDouble', now, g.get('LastBumperNoteTime'))
restart = g.math('Greater_DoubleDouble', elapsed, .85)
increment = g.math('Add_IntInt', g.get('BumperNoteIndex'), 1)
bounded = g.call('/Script/Engine.KismetMathLibrary:Min', A=increment, B=len(sounds) - 1).find_output_pin('ReturnValue')
selected = g.call('/Script/Engine.KismetMathLibrary:SelectInt', A=0, B=bounded, bPickA=restart)
g.set('BumperNoteIndex', selected.find_output_pin('ReturnValue'))
g.set('LastBumperNoteTime', now)
if 'BumperComboCount' in B.list_variables(table):
    first = g.math('EqualEqual_IntInt', g.get('BumperNoteIndex'), 0)
    total = g.math('Add_IntInt', g.get('BumperComboCount'), 1)
    g.set('BumperComboCount', g.call('/Script/Engine.KismetMathLibrary:SelectInt', A=1, B=total, bPickA=first).find_output_pin('ReturnValue'))
# Array_Get has a wildcard item output parameter.
note = g.call(array + 'Array_Get', TargetArray=g.get('BumperNotes'), Index=g.get('BumperNoteIndex'))
g.action(game + 'PlaySound2D', Sound=note.find_output_pin('Item'))
B.compile_blueprint(table)
for graph_name, ids in [('EventGraph', ('|SetHits', '|SetSplitHits')), ('CopyHit', ('|SpawnBumperHitFX',))]:
    g = Graph(table, graph_name)
    matches = [n for n in B.find_nodes(g.g) if B._get_node_info(n).type_id in ids]
    assert len(matches) == len(ids)
    for node in matches:
        after(g, node, 'PlayBumperNote')
B.compile_blueprint(table, warnings_as_errors=True)
defaults = B.get_default_object(table)
defaults.set_editor_property('BumperNotes', sounds)
defaults.set_editor_property('LastBumperNoteTime', -10.0)

variable(HUD, 'BumperAudioTestLayout', 'bool')
B.compile_blueprint(HUD)
g = Graph(HUD, 'SeedBumperAudioTest', True)
g.tail, _ = g.branch(g.get('BumperAudioTestLayout'))
for cell in cells:
    g.action(array + 'Array_Set', TargetArray=g.get('CellTypes'), Index=cell, Item=1, bSizeToFit=False)
    g.action(ROOT + 'BP_PinballTable.BP_PinballTable_C:SetObstacle', self=g.get('Table'), Index=cell, Type=1)
B.compile_blueprint(HUD)
g = Graph(HUD, 'InitializeBoard')
after(g, g.old('K2Node_SpawnActorFromClass_4'), 'SeedBumperAudioTest')
B.compile_blueprint(HUD, warnings_as_errors=True)
B.get_default_object(HUD).set_editor_property('BumperAudioTestLayout', True)
for bp in (table, HUD):
    assert u.EditorAssetLibrary.save_loaded_asset(bp, False)
u.log('BUMPER_AUDIO_INSTALLED')



