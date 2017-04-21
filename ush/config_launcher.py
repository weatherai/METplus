from __future__ import print_function
"""!Creates the initial METplus directory structure, loads information into each job.

This module is used to create the initial METplus conf file in the
first METplus job via the metplus.config_launcher.launch().  
The metplus.config_launcher.load() then reloads that configuration.  
The launch() function does more than just create the conf file though.  
It creates several initial files and  directories and runs a sanity check 
on the whole setup.

The METplusLauncher class is used in place of a produtil.config.ProdConfig
throughout the METplus system.  It can be used as a drop-in replacement
for a produtil.config.ProdConfig, but has additional features needed to
support sanity checks, and initial creation of the METplus system.
"""

##@var __all__
# All symbols exported by "from metplus.launcher import *"
__all__=['load','launch','parse_launch_args','load_baseconfs']

import os, re, sys, collections, random
import produtil.fileop, produtil.run, produtil.log
from produtil.fileop import isnonempty
from produtil.run import run, exe
from produtil.log import jlogger
from os.path import dirname, realpath
from random import Random
from produtil.config import ProdConfig

baseinputconfs = ['metplus.conf','metplus.override.conf']

##@var HOMEmetplus
# The METplus installation directory
HOMEmetplus=None

##@var USHmetplus
# The ush/ subdirectory of the METplus installation directory
USHmetplus=None

##@var PARMmetplus
# The parameter directory
PARMmetplus=None

if os.environ.get('HOMEmetplus',''):  HOMEmetplus=os.environ['HOMEmetplus']
if os.environ.get('USHmetplus',''):   USHmetplus=os.environ['USHmetplus']
if os.environ.get('PARMmetplus',''):  PARMmetplus=os.environ['PARMmetplus']

# Based on HOMEmetplus, Will set USHmetplus, or PARMmetplus if not
# already set in the environment.
if HOMEmetplus is None:
    guess_HOMEmetplus=dirname(dirname(realpath(__file__)))
    USHguess=os.path.join(guess_HOMEmetplus,'ush')
    PARMguess=os.path.join(guess_HOMEmetplus,'parm')
    if os.path.isdir(USHguess) and os.path.isdir(PARMguess):
        if USHmetplus is None: USHmetplus=USHguess
        if PARMmetplus is None: PARMmetplus=PARMguess
else:
    if os.path.isdir(HOMEmetplus):
        if USHmetplus is None: USHmetplus=os.path.join(HOMEmetplus,'ush')
        if PARMmetplus is None: PARMmetplus=os.path.join(HOMEmetplus,'parm')
    else:
        print("$HOMEmetplus is not a directory: {} \nPlease set $HOMEmetplus " \
               "in the environment.".format(HOMEmetplus), file=sys.stderr)
        sys.exit(2)

#print("guess_HOMEmetplus is: {}",guess_HOMEmetplus)
#print("USHmetplus is: {}",USHmetplus)
#print("PARMmetplus is: {}",PARMmetplus)

# For METplus, this is assumed to already be set.
if USHmetplus not in sys.path:
    sys.path.append(USHmetplus)

#def parse_launch_args(args,usage,logger,PARMmetplus=None):
# This is intended to be use to gather all the conf files on the
# command line, along with overide options on the command line.
# This includes the default conf files metplus.conf, metplus.override.conf
# along with, -c some.conf and any other conf files...
# These are than used by def launch to create a single metplus final conf file
# that would be used by all tasks.
def parse_launch_args(args, usage, logger):

    parm=os.path.realpath(PARMmetplus)

    # Files in this list, that don't exist or are empty,
    # will be silently ignored.
    #infiles=[ os.path.join(parm, 'metplus.conf'),
    #          os.path.join(parm, 'metplus.override.conf')
    #         ]
    infiles=list()
    for filename in baseinputconfs:
        infiles.append(os.path.join(parm,filename))

    moreopt = collections.defaultdict(dict)

    if args is None: return (parm,infiles,moreopt)

    # Now look for any option and conf file arguments:
    bad=False
    for iarg in xrange(len(args)):
        logger.info(args[iarg])
        m=re.match('''(?x)
          (?P<section>[a-zA-Z][a-zA-Z0-9_]*)
           \.(?P<option>[^=]+)
           =(?P<value>.*)$''',args[iarg])
        if m:
            logger.info('Set [%s] %s = %s'%(
                    m.group('section'),m.group('option'),
                    repr(m.group('value'))))
            moreopt[m.group('section')][m.group('option')]=m.group('value')
        elif os.path.exists(args[iarg]):
            logger.info('%s: read this conf file'%(args[iarg],))
            infiles.append(args[iarg])
        else:
            bad=True
            logger.error('%s: invalid argument.  Not an config option '
                         '(a.b=c) nor a conf file.'%(args[iarg],))
    if bad:
        sys.exit(2)

    for file in infiles:
        if not os.path.exists(file):
            logger.error(file+': conf file does not exist.')
            sys.exit(2)
        elif not os.path.isfile(file):
            logger.error(file+': conf file is not a regular file.')
            sys.exit(2)
        elif not produtil.fileop.isnonempty(file):
            logger.warning(
                    file+': conf file is empty.  Will continue anyway.')
        logger.info('Conf input: '+repr(file))
    return (parm,infiles,moreopt)

# This is intended to be used to create and write a final conf file
# that is used be all tasks .... though METplus isn't being run
# that way .... instead METplus tasks need to be able to run stand-alone
# so each task needs to be able to initialize the conf files.
def launch(file_list,moreopt,cycle=None,init_dirs=True,
           prelaunch=None):

    for filename in file_list:
        if not isinstance(filename,basestring):
            raise TypeError('First input to metplus.config.for_initial_job '
                            'must be a list of strings.')

    conf=ProdConfig()
    logger=conf.log()

    for filename in file_list:
        logger.info("%s: Parse this file" % (filename,))
        conf.read(filename)

    produtil.fileop.makedirs(conf.getdir('WORKmetplus'),logger=logger)

    #logger.info('Expand certain [dir] values to ensure availability ')
    #            'before vitals parsing.
    # frimel: Especially before vitals parsing. THIS IS ONLY NEEDED in
    # order to define the vit dictionary and use of vit|{somevar} in the
    # conf file.
    for var in ( 'WORKmetplus', 'HOMEmetplus'):
        expand=conf.getstr('dir',var)
        logger.info('Replace [dir] %s with %s'%(var,expand))
        conf.set('dir',var,expand)

    #conf.set('dir','HOMEmetplus',HOMEmetplus)

    #writes the metplus conf used by all tasks.
    confloc=conf.getloc('CONFmetplus')
    logger.info('%s: write primary metplus.conf here'%(confloc,))
    with open(confloc,'wt') as f:
        conf.write(f)

    return conf

def load(filename):
    """!Loads the METplusLauncher created by the launch() function.

    Creates an METplusConfig object for a METplus workflow that was
    previously initialized by metplus.config_launcher.launch.  
    The only argument is the name of the config file produced by 
    the launch command.

    @param filename The metplus*.conf file created by launch()"""

    conf=ProdConfig()
    conf.read(filename)
    logger=conf.log()

    #cycle=conf.cycle
    #assert(cycle is not None)
    #strcycle=cycle.strftime('%Y%m%d%H')
    #logger.info('Running cycle: '+cycle.strftime('%Y%m%d%H'))

    WORKmetplus=conf.getdir('WORKmetplus')

    return conf

# A METplus Demonstration work-around ...
# Assumes and reads in only baseconfs and -c add_conf_file
# This allows calling from both master_met_plus.py and via
# the command line from an individual module, such as series_by_lead.py
def load_baseconfs(add_conf_file=None):
    """ Loads the following conf files """

    parm=PARMmetplus

    #baseconfs=[ os.path.join(parm, 'metplus.conf'),
    #          os.path.join(parm, 'metplus.override.conf')
    #         ]

    conf=ProdConfig()
    logger=conf.log()

    for filename in baseinputconfs:
        conf_file=os.path.join(parm,filename)
        logger.info("%s: Parse this file" % (conf_file,))
        conf.read(conf_file)

    # Read the added conf file last, after the base input confs.
    # Since these settings will override.
    if add_conf_file:
        conf_file=set_conf_file_path(add_conf_file)
        logger.info("%s: Parse this file" % (conf_file,))
        conf.read(conf_file)

    return conf

# This is meant to be used with the -c option in METplus
# for backward compatability, since users using the -c option
# are not required to add path information and the previous
# constants object found it since it was pulled in via the import
# statement and the parm directory was defined in the PYTHONPATH
def _set_conf_file_path(conf_file):
    """Do not call this.  It is an internal implementation routine.
    It is only used internally and is called when adding an 
    additional conf using the -c command line option.

    Adds the path information to the conf file if there isn't any.
    """
    parm = PARMmetplus

    # Determine if add_conf_file has path information /path/to/file.conf
    # If not head than there is no path information, only a filename,
    # so assUme the conf file is in the parm directory, and add that
    # parm path information
    head, tail = os.path.split(conf_file)
    if not head:
        new_conf_file=os.path.join(parm,conf_file)
        return new_conf_file

    return conf_file

# THIS IS NOT USED, meant for internal dev testing.
def test_gen_conf(file_list,cycle=None):

    for filename in file_list:
        if not isinstance(filename,basestring):
            raise TypeError('First input to metplus.config.for_initial_job '
                            'must be a list of strings.')
    conf=ProdConfig()
    logger=conf.log()

    for filename in file_list:
        logger.info("%s: parse this file"%(filename,))
        conf.read(filename)

    produtil.fileop.makedirs(conf.getdir('WORKmetplus'),logger=logger)

    for var in ( 'WORKmetplus', 'HOMEmetplus' ):
        expand=conf.getstr('dir',var)
        logger.info('Replace [dir] %s with %s'%(var,expand))
        conf.set('dir',var,expand)

    #writes metplus.conf used by all tasks.
    confloc=conf.getloc('CONFmetplus')
    logger.info('%s: write metplus.conf here'%(confloc,))
    with open(confloc,'wt') as f:
        conf.write(f)

    return conf

# THIS IS NOT USED, meant for internal dev testing.
def test_metplus_launch_args(args,logger,usage,PARMmetplus=None):
    if len(args)<2 or ( PARMmetplus is None and len(args)<3):
        usage(logger=logger)
        sys.exit(2)
    stid=args[0].upper()
    logger.info('Running Storm ID is '+repr(stid))
    logger.info('VX test infoX')
    logger.debug('VX test debugX')
    logger.error('VX test errorX')

    case_root='HISTORY'
    parm='/path/to/METplus/parm'
    infiles=['/path/to/METplus/parm/metplus_input.conf',
             '/path/to/METplus/parm/metplus.conf',
             '/path/to/METplus/parm/metplus_basic.conf',
             '/path/to/METplus/parm/system.conf',
             '../../frimel.conf.lfs2']

    stid='18L'
    moreopt={'config': {'HOMEmetplus': '/path/to/METplus', 'EXPT': 'metplus_trunk'}}

    return (case_root,parm,infiles,stid,moreopt)



