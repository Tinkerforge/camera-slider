#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
from subprocess import check_output

def system(cmd):
    print 'SYSTEM', cmd

    if os.system(cmd) != 0:
        sys.exit(1)

os.system('rm gphoto2')
os.system('rm *.dylib')
os.system('rm -rf camlibs && mkdir -p camlibs')
os.system('rm -rf iolibs && mkdir -p iolibs')

def change_id(name):
    print 'CHANGE_ID', name
    system('install_name_tool -id @executable_path/{0} {0}'.format(name))

def change_dep(name, lib):
    print 'CHANGE_DEP', name, lib
    system('install_name_tool -change /opt/local/lib/{1} @executable_path/{1} {0}'.format(name, lib))

def copy_deps(name):
    libs = check_output("otool -L {0} | tail -n +2 | awk '{{ print $1 }}' | sed -n '/^\/opt\/local\/lib/p' | sed -e 's/^\/opt\/local\/lib\///g'".format(name), shell=True).split('\n')

    print 'COPY_DEPS', name, ':', libs

    for lib in libs:
        if len(lib) > 0 and lib != name:
            change_dep(name, lib)
            copy_lib(lib)

def copy_lib(name):
    print 'COPY_LIB', name

    if not os.path.exists(name):
        system('cp /opt/local/lib/{0} {0} && chmod 755 {0}'.format(name))
        change_id(name)
        copy_deps(name)

system('cp /opt/local/bin/gphoto2 gphoto2 && chmod 755 gphoto2')
copy_deps('gphoto2')

for camlib_so in os.listdir('/opt/local/lib/libgphoto2/2.5.7'):
    camlib_dylib = camlib_so.replace('.so', '.dylib')
    system('cp /opt/local/lib/libgphoto2/2.5.7/{0} camlibs/{1} && chmod 755 camlibs/{1}'.format(camlib_so, camlib_dylib))
    copy_deps('camlibs/{0}'.format(camlib_dylib))

for iolib_so in os.listdir('/opt/local/lib/libgphoto2_port/0.12.0'):
    iolib_dylib = iolib_so.replace('.so', '.dylib')
    system('cp /opt/local/lib/libgphoto2_port/0.12.0/{0} iolibs/{1} && chmod 755 iolibs/{1}'.format(iolib_so, iolib_dylib))
    copy_deps('iolibs/{0}'.format(iolib_dylib))

