
import logging
import sh, os, subprocess

import PblAnalytics
from PblCommand import PblCommand
from PblProjectCreator import requires_project_dir
from LibPebblesCommand import (NoCompilerException, BuildErrorException,
                               AppTooBigException)

class PblWafCommand(PblCommand):
    """ Helper class for build commands that execute waf """

    waf_cmds = ""

    def waf_path(self, args):
        return os.path.join(os.path.join(self.sdk_path(args), 'Pebble'), 'waf')
    
    def _getMemoryUsage(self, args):
        """ Return the memory usage for the current app. 
        
        retval: (textSize, dataSize, bssSize)
        """
        cmdArgs = [os.path.join(self.sdk_path(args), "arm-cs-tools", "bin",
                "arm-none-eabi-size"), os.path.join("build", "pebble-app.elf")]
        pobj = subprocess.Popen(cmdArgs, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        (stdout, stderr) = pobj.communicate()
        retval = pobj.returncode

        if retval == 0:
            (tSize, dSize, bSize) = [int(x) for x in \
                                     stdout.splitlines()[1].split()[:3]]
        else:
            logging.error("command line %s failed. stdout: %s, stderr: %s" %
                          cmdArgs, stdout, stderr)
            (tSize, dSize, bSize) = (None, None, None)
            
        return (tSize, dSize, bSize)
        

    @requires_project_dir
    def run(self, args):
        os.environ['PATH'] = "{}:{}".format(os.path.join(self.sdk_path(args), 
                                "arm-cs-tools", "bin"), os.environ['PATH'])
        
        cmdLine = self.waf_path(args) + " " + self.waf_cmds
        retval = subprocess.call(cmdLine, shell=True)
        
        # If an error occurred, we need to do some sleuthing to determine a
        # cause. This allows the caller to post more useful information to
        # analytics. We normally don't capture stdout and stderr using Poepn()
        # because you lose the nice color coding produced when the command
        # outputs to a terminal directly.
        #
        # But, if an error occurs, let's run it again capturing the output
        #  so we can determine the cause
          
        if (retval):
            pobj = subprocess.Popen(cmdLine.split(), stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
            (stdout, stderr) = pobj.communicate()
                 
            # Look for common problems
            if "Could not determine the compiler version" in stderr:
                raise NoCompilerException
            
            elif "region `APP' overflowed" in stderr:
                raise AppTooBigException
            
            else:
                raise BuildErrorException
            
        else:
            # No error, get the size of the app so we can send it to analytics
            (textSize, dataSize, bssSize) = self._getMemoryUsage(args)
            if textSize is not None:
                PblAnalytics.appSizeEvt(textSize=textSize, dataSize=dataSize,
                                     bssSize = bssSize)
            
        return 0

    def configure_subparser(self, parser):
        PblCommand.configure_subparser(self, parser)

class PblBuildCommand(PblWafCommand):
    name = 'build'
    help = 'Build your Pebble project'
    waf_cmds = 'configure build'

class PblCleanCommand(PblWafCommand):
    name = 'clean'
    help = 'Clean your Pebble project'
    waf_cmds = 'distclean'
