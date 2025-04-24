from microscope_control.Constants import *
import pandas as pd 
from datetime import datetime
import os
from glob import glob

PATH_DATA_SETS = r"G:/My Drive/Ba Tagging/data/img/"
SETUP_NAME = "Barium-Tagging"
OPERATOR = "Pablo Herrero"
EXCITATION_FILTER = "Center-527nm_Width-22nm",
DOUBLE_FILTER = "Center-561nm_Width-21nm"
LEFTOVER_FILTER = "Center-500nm_Width-29nm",
LASER_WAVELENGTH = "515nm"
LASER_SOURCE = "TOptica"
DICHROIC_MIRROR_CUTTOFF = "550nm"
N_DMIRRORS = 2
MICROSCOPE_OBJECTIVE = "Mitutoyo_50x_NA_0.5"
exposure = 10
EXPOSURE_TIME = str(exposure)+'s'

DICT_MICROSCOPE_OBJECTIVE = {1: "Mitutoyo_50x_NA_0.5",
                             2: "Nikon_60x_NA_0.95"}

DICT_LASER_SOURCE = {1: "TOptica",
                     2: "Diode",
                     3: "Off"}

DICT_LASER_WAVELENGTH = {"TOptica": 515.6,
                         "Diode": 518.7,
                         "Off": 0}


df_settings = pd.DataFrame()

def namestr(obj, namespace):
    """Return the name of the variable in the namespace"""

    return [name for name in namespace if namespace[name] is obj]

def print_settings(dfsettings):
    print()
    print(dfsettings)
    print()

def write_settings_static(fout):

    settings = [SETUP_NAME, OPERATOR,
                LASER_WAVELENGTH, LASER_SOURCE,
                DICHROIC_MIRROR_CUTTOFF, N_DMIRRORS,
                MICROSCOPE_OBJECTIVE, EXPOSURE_TIME]
    # Make a list of strings with the name of the variable and its value:
    fsettings = [f'{namestr(v, globals())[0]}: {v}' for v in settings]  

    with open(fout, 'w') as fo:
        fo.write(';\n'.join(fsettings))

def write_settings(fout, dfsettings):
    fileout = fout + '\settings.json'
    print('Writing settings in ', fileout)
    dfsettings.to_csv(fileout, sep=':', header=False, index=False)

def read_settings(fin):
    fin = fin.replace('\\', '/')
    print(fin)
    df_settings = pd.read_csv(fin, sep=':', names=['setting', 'value'], )
    return df_settings


def edit_dropdown(key, dictionary, df_edit):
    dropdowns = {'laser': DICT_LASER_SOURCE, 'obj': DICT_MICROSCOPE_OBJECTIVE}
    current_dict = dropdowns[dictionary]
    flag_stop = True
    while flag_stop:
        print(f'\nEditing {df_edit.setting[key]} = {df_edit.value[key]}')
        print(current_dict)
        print("\nPress 'q' to quit\n" )

        subkey = input('\nSelect option\n') 
        if subkey == 'q':
            flag_stop = False
        elif int(subkey) in current_dict:
            subkey = int(subkey)
            df_edit.loc[key, 'value'] = current_dict[subkey]
            flag_stop = False 
        else:
            print("invalid key")
    
    

def edit_settings(df_settings):
    # df_edit = df_settings[ df_settings ['setting'] != 'EXPOSURE_TIME']    
    df_edit = df_settings[~df_settings['setting'].isin(['EXPOSURE_TIME', 'POWER(uW)'])].copy()      # Blocked settings (set automatically)
    df_block = df_settings[df_settings['setting'].isin(['EXPOSURE_TIME', 'POWER(uW)'])].copy()
    flag_stop = True
    while flag_stop:
        print(df_settings)
        print("\nPress 'q' to quit\n" )
        key = input('\nSelect key\n')
        if key == 'q':
            flag_stop = False
        elif int(key) in df_edit.index:
            key = int(key)
            if (df_edit.setting[key] == 'LASER_SOURCE'):
                edit_dropdown(key, 'laser', df_edit)
                # new_wv = DICT_LASER_WAVELENGTH[]
            elif  (df_edit.setting[key] == 'MICROSCOPE_OBJECTIVE'):
                edit_dropdown(key, 'obj', df_edit)
            else:
                print(f'\nEditing {df_edit.setting[key]} = {df_edit.value[key]}')
                value = input('\nEnter value:\n')
                df_edit.loc[key, 'value'] = value
        else:
            print("invalid or blocked key")
       
        df_settings = pd.concat([df_edit, df_block])
    
    return df_settings

def add_settings_value(df_setting, setting, value):
    df_setting['nindex'] = df_setting.index
    df_setting = df_setting.set_index('setting', drop=False)
    df_setting.loc[setting, 'value'] = value
    df_setting = df_setting.set_index('nindex', drop=True)
    return df_setting
    
def find_recent_settings():
    finds = glob(PATH_DATA_SETS+'**/**/**/**/settings.json')
    dirs = [f[:len(PATH_DATA_SETS)+13] for f in finds]
    datestr = [os.path.split(d)[1] for d in dirs]
    dates = [datetime.strptime(dstr, "%d-%m-%y") for dstr in datestr]
    dir_recent = datetime.strftime(max(dates), "%d-%m-%y")
    for d in dirs:
        if dir_recent in d: path_recent = d
    recent_settings_path = glob(path_recent+'/**/**/settings.json')[-1]
    return recent_settings_path  

# G:\My Drive\Ba Tagging\data\img\sets\08-12-24\Rhodamine-B 50 µM\1
# G:/My Drive/Ba Tagging/data/img/10-12-24/**/**/