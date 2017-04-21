#!/usr/bin/env python
from __future__ import print_function

import os, sys, re, logging, collections, getopt

import produtil.setup
#import produtil.log
#import produtil.fileop, produtil.numerics, produtil.config
#from produtil.config import ProdConfig
#from produtil.numerics import to_datetime
#import constants_pdef as P
import met_util as util
import config_launcher

## The logging.Logger for log messages
logger=None

def usage(logger=None):

    if logger:
        logger.critical('Invalid arguments to master_met_plus.py.  Exiting.')

    print ('''
Usage: master_met_plus.py [ -c /path/to/additional/conf_file] [options]

Optional arguments:
section.option=value -- override conf options on the command line
/path/to/parmfile.conf -- additional conf files to parse

Exiting due to incorrect arguments.''')
    sys.exit(2)

def main():
    '''
        Master MET+ script that invokes the necessary Python scripts
        to perform various activities, such as series analysis.
    '''

    produtil.log.jlogger.info('Top of master_met_plus')
    logger = logging.getLogger('master_met_plus')
    logger.info('logger Top of master_met_plus.')

    # if option is followed by : or = indicates option requires an argument
    short_opts = "c:h"
    long_opts  = ["constants=",
                  "help"]

    # All command line input, get options and arguments
    try:
        opts, args = getopt.gnu_getopt(sys.argv[1:], short_opts, long_opts)
    except getopt.GetoptError as err:
        print(str(err))
        usage('SCRIPT IS EXITING DUE TO UNRECOGNIZED COMMAND LINE OPTION')

    # NOTE: if -c option is used, than this conf file will be the
    # last confile read, regardless of the order of multiple conf files
    # given on the command line.
    #
    # opts=[('-h',''),('-c','path/to/file.conf')]

    config_file=None
    for k, v in opts:
        if  k in ('-c', '--constants'):
            #adds the conf file to the list of arguments.
            args.append(config_launcher.set_conf_file_path(v))
            config_file=v
        elif  k in ('-h', '--help'):
            usage()
        else:
            assert False, "UNHANDLED OPTION"

    # parm, is path to parm directory
    # infiles, list of input conf files to be read and processed
    # moreopt, dictionary of conf file settings, passed in from command line.
    if not args: args=None
    (parm,infiles,moreopt) = \
        config_launcher.parse_launch_args(args,usage,logger)

    # Currently metplus is not handling cycle.
    # Therefore can not use conf.timestrinterp and
    # some conf file settings ie. {[a|f]YMDH} time settings.
    cycle=None
    p = config_launcher.launch(infiles, moreopt, cycle=cycle)

    # Used for logging
    cur_filename = sys._getframe().f_code.co_filename
    cur_function = sys._getframe().f_code.co_name
   
    logger = util.get_logger(p)
    #This is available in each subprocess from os.system BUT
    #we also set it in each process since they may be called stand alone.
    os.environ['MET_BASE'] = p.getdir('MET_BASE')

    # Get the list of processes to call
    process_list = util.getlist(p.getstr('config','PROCESS_LIST'))

    # Get the name of the config file to use
    # This is either None, or everything after the -c option.
    # It will include any path information, absolute or relative,
    # if it was provided, ie. path/filename
    #config_file = p_p.getConfigFilePath()

    for item in process_list:

        if config_file == None:
            cmd = "%s" % item
            logger.info("INFO | [" + cur_filename +  ":" + cur_function + "] | " + "Running: " + cmd)
            ret = os.system(cmd)
            if ret != 0:
                logger.error("ERROR | [" + cur_filename +  ":" + cur_function + "] | " + "Problem executing: " + cmd)
                exit(0)
        else:
            cmd = "%s -c %s" % (item, config_file)
            logger.info("INFO | [" + cur_filename +  ":" + cur_function + "] | " + "Running: " + cmd)
            ret = os.system(cmd)
            if ret != 0:
                logger.error("ERROR | [" + cur_filename +  ":" + cur_function + "] | " + "Problem executing: " + cmd)
                exit(0)

if __name__ == "__main__":
    try:
        # Setting jobname as just an FYI ... problably shouldn't set so
        # as not to confuse since DBN is not being used ... Default jobname,
        # if not defined, in log is 'NO-NAME'
        # Assuming the jlogfile environment variable set and path exists
        produtil.setup.setup(send_dbn=False, jobname='run-METplus')
        produtil.log.postmsg('master_met_plus is starting')
        main()
        produtil.log.postmsg('master_met_plus completed')
    except Exception as e:
        produtil.log.jlogger.critical(
            'master_metplus  failed: %s'%(str(e),),exc_info=True)
        sys.exit(2)



