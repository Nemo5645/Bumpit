"""Import the rendered workshop cues, preserving fixed event asset paths."""
from pathlib import Path
import unreal as u
project=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir()))
tasks=[]
for wav in sorted((project/'SoundSources/Workshop').glob('*.wav')):
    task=u.AssetImportTask()
    task.filename=str(wav)
    task.destination_path='/Game/Bumpit/Audio/Workshop'
    task.destination_name='S_'+wav.stem
    task.automated=task.replace_existing=task.save=True
    tasks.append(task)
u.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
for task in tasks:
    asset=u.load_asset(task.destination_path+'/'+task.destination_name)
    assert isinstance(asset,u.SoundWave),task.filename
    asset.set_editor_property('looping',task.destination_name.split('_')[1] in ('01','09','17','24','51'))
    assert u.EditorAssetLibrary.save_loaded_asset(asset,False)
u.log(f'WORKSHOP_IMPORTED {len(tasks)}')
