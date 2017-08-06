import sys

from cx_Freeze import setup, Executable

sys.argv.append('build_exe')

options = {
    'build_exe': {

        'excludes': ['asyncio', 'lib2to3'],
        'include_msvcr': True,
        'zip_include_packages': '*',
        'zip_exclude_packages': '',
    }
}

executables = [
    Executable('main.py', base='Console', targetName = 'urw.exe')
]

setup(name='urw_stat_roller',
      version = '2.0',
      description = 'Stat roller for UnReal World',
      options = options,
      executables = executables)
