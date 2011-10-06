#!/usr/bin/env python
"""
    rsync_backup - A wrapper for creating incremental backups using rsync
    Copyright (C) 2011  Dominik Bruhn

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

"""
Wrapper around rsync which creates incremental backups using the 'link-dest'
feature of rsync, so it is creating hardlinks. It checks whether the
destiation is correctly mounted to ensure that the backup goes into the right
location. It saves the log-files of each backup together with the backup itself
for later debugging. The script features a 'statdir' which can help you to
track when the last backup was done even if the target-drive is currently not
plugged in. This works by writing the backup-timestamps into a folder on your
harddisk. To distinguish between mulptile drives, you must first create a
'.drive_id' file in the root of the device which contains a unique-identifier
of this backup-device.
The script is designed for use as a user to backup the home-directory or parts
of it. It is not meant to backup a whole system. 

Instructions:
    - Set LOGFILE to a appropriate location
    - Add one or multiple backup-jobs to the CONFIG array
"""

CONFIG=[
    {
        'name': 'home-dell', #Identifier for the Backup, simple characters only
        'source': '/home/dominik/', #Source Directory, / gets appended if needed
        'target': '/media/BACKUP/home-dell', #Target Directory
        'mountpoint': '/media/BACKUP/', #Mountpoint which is checked if mounted
        'exclude-from': '/home/dominik/.config/backup.exclude',#Exclude-Filelist
        'statdir': '/home/dominik/.cache' #Directory for statfiles
    }
]

LOGFILE="/home/dominik/.cache/backup.log"

import logging
from datetime import datetime
import os
from os import path
import sys
import subprocess

LOG = logging.getLogger("backup.main")


def doBackup(c):
    LOG.info("Runing Backup for config %s", c)
    date=datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

    if (c['source'][-1]!='/'):
        c['source']=c['source']+"/"

    target_temp = path.join(c['target'], date+"_incomplete")
    target= path.join(c['target'], date)
    logfile=path.join(c['target'], date+'.log')

    #Check if mounted
    if (not path.ismount(c['mountpoint'])):
        LOG.error("Target %s is not mounted", c['mountpoint'])
        sys.exit(1)

    #Check target exists and writeable
    if(not path.exists(c['target'])):
        LOG.error("Target %s does not exist", c['target'])
        sys.exit(2)

    if(not path.isdir(c['target'])):
        LOG.error("Target %s is not a directory", c['target'])
        sys.exit(2)

    if(not os.access(c['target'], os.W_OK)):
        LOG.error("Target %s is not writeable", c['target'])

    #Try to find the most recent backup
    dirs = sorted(os.listdir(c['target']), reverse=True)
    olddir=None
    for colddir in dirs:
        if ('incomplete' in colddir):
            continue
        if ('log' in colddir):
            continue

        olddir=colddir
        break

    if (olddir is None):
        LOG.info("Found no olddir, must be firstbackup")
    else:
        olddir=os.path.join(c['target'], olddir)
        LOG.info("Found olddir %s", olddir)

    #Try to identify drive
    idfile = path.join(c['mountpoint'], '.drive_id')
    if (path.isfile(idfile) and os.access(idfile, os.R_OK)):
        fidfile = open(idfile, 'r')
        driveid = fidfile.readline().strip()
        fidfile.close()
    else:
        driveid = None

    #Build params
    p = [
         "/usr/bin/rsync",

        '-a', #Archive
        '-v', #Verbose
        '--stats', #Stats
        '-n',  #Dry
        '-x', #One File System
        '--delete',
        '--delete-excluded',
   ]

    if ('exclude-from' in c):
        p.append('--exclude-from='+c['exclude-from'])

    if (olddir is not None):
        p.append('--link-dest='+olddir)

    p.extend([
        c['source'],
        target_temp
    ])

    #Opening log-file
    flog=open(logfile, 'w')
    flog.write("$%s\n" % (p))

    #Run Rsync
    LOG.info("Runnning rsync: '%s'", p)

    rsync = subprocess.Popen( p, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT)
    while True:
        rsync_line = rsync.stdout.readline()
        exitcode = rsync.poll()
        if (not rsync_line) and (exitcode is not None):
            break
        rsync_line = rsync_line[:-1]
        LOG.debug("%s", rsync_line)
        flog.write(rsync_line+"\n")

    flog.close()
    if (exitcode!=0):
        LOG.error("Rsync failed exitcode was %d", exitcode)
        sys.exit(10)

    LOG.info("Rsync finished")

    #Rename directory
    LOG.info("Renaming %s to %s", target_temp, target)
    os.rename(target_temp, target)

    if (driveid is not None):
        #Save stats
        statfile=os.path.join(c['statdir'], driveid+"_"+c['name'])
        LOG.info("Generating stat-file %s", statfile)
        fstats=open(statfile, "w")
        statcmd="/bin/ls -ldh "+c['target']+"*/"
        LOG.info("Stat-command is '%s'", statcmd)
        p = subprocess.call(statcmd, stdout=fstats, shell=True)
        LOG.info("Generation returned %d", p)
        if (p!=0):
            LOG.error("Could not generate stat-file %s", statfile)
        fstats.close()


if __name__ == '__main__':
    ###########################
    # Set Up Logging
    ###########################
    # set up logging to file - see previous section for more details
    logging.basicConfig(level=logging.DEBUG,
        format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
        datefmt='%m-%d %H:%M',
        filename=LOGFILE)

    # define a Handler which writes INFO messages or higher to the sys.stderr
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    # set a format which is simpler for console use
    formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
    # tell the handler to use this format
    console.setFormatter(formatter)
    # add the handler to the root logger
    logging.getLogger('').addHandler(console)

    console.setLevel(logging.DEBUG)

    for c in CONFIG:
        doBackup(c)
