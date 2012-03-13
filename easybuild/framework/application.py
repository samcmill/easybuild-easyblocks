##
# Copyright 2009-2012 Stijn Deweirdt, Dries Verdegem, Kenneth Hoste, Pieter De Baets, Jens Timmerman
#
# This file is part of EasyBuild,
# originally created by the HPC team of the University of Ghent (http://ugent.be/hpc).
#
# http://github.com/hpcugent/easybuild
#
# EasyBuild is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation v2.
#
# EasyBuild is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with EasyBuild.  If not, see <http://www.gnu.org/licenses/>.
##
from distutils.version import LooseVersion
import glob
import os
import shutil
import time

import easybuild
from easybuild.tools.build_log import initLogger, removeLogHandler, EasyBuildError
from easybuild.tools.config import sourcePath, buildPath, installPath
from easybuild.tools.filetools import unpack, patch, run_cmd, convertName
from easybuild.tools.module_generator import ModuleGenerator
from easybuild.tools.modules import Modules
from easybuild.tools.toolkit import Toolkit


class Application:
    """
    This is the dummy Application class.
    All other Application classes should be inherited from this one
    """

    ## INIT
    def __init__(self,name=None,version=None,newBuild=True,debug=False):
        """
        Initialize the Application instance.
        """
        self.log=None
        self.logfile=None
        self.loghandler=None
        self.logdebug=debug
        
        self.patches=[]
        self.src=[]
        self.dep=[]
        self.tk=None
        
        self.builddir=None
        self.installdir=None

        ## final version
        self.installversion='NOT_VALID'
        
        ## valid moduleclasses
        self.validmoduleclasses=['base','compiler','lib']

        ## vaild stop options
        self.validstops=['cfg','source','patch','configure','make','install','test','postproc','cleanup','packages']

        ## mandatory cfg
        self.mandatory=['name','version','homepage','description']

        self.cfg={
          'name':[None,"Name of software"],
          'version':[None,"Version of software"],
          'easybuildVersion': [None, "EasyBuild-version this spec-file was written for"],
          'group':[None,"Name of the user group for which the software should be available"],
          'versionsuffix':['','Additional suffix for software version (placed after toolkit name)'],
          'versionprefix':['','Additional prefix for software version (placed before version and toolkit name)'],                  
          'runtest':[None,'Indicates if a test should be run after make. Default: argument after make (for eg make test)'],
          'preconfigopts':['','Extra options pre-passed to configure.'],
          'configopts':['','Extra options passed to configure (Default already has --prefix)'],
          'premakeopts':['','Extra options pre-passed to make.'],
          'makeopts':['','Extra options passed to make (Default already has -j X)'],
          'installopts':['','Extra options for installation (Default: nothing)'],
          'moduleclass':['base','Module class to be used for this software (Default: base) (Valid: %s)'%self.validmoduleclasses],
          'moduleforceunload':[False,'Force unload of all modules when loading the package (Default: False)'],
          'moduleloadnoconflict':[False,"Don't check for conflicts, unload other versions instead (Default: False)"],
          'startfrom':[None,'Path to start the make in. If the path is absolute, use that path. If not, this is added to the guessed path.'],
          'onlytkmod':[False,'Boolean/string to indicate if the toolkit should only load the enviornment with module (True) or also set all other variables (False) like compiler CC etc (If string: comma separated list of variables that will be ignored). (Default: False)'],
          'stop':[None,'Keyword to halt the buildprocess at certain points. Valid are %s'%self.validstops],
          'homepage':[None,'The homepage of the software'],
          'description':[None,'A short description of the software'],
          'parallel':[None, '(Default: based on the number of cores and restrictions in ulimit)'],
          'keeppreviousinstall':[False,'Boolean to keep the previous installation with identical name. Default False, expert s only!'],
          'cleanupoldbuild':[True,'Boolean to remove (True) or backup (False) the previous build directory with identical name or not. Default True'],
          'cleanupoldinstall':[True,'Boolean to remove (True) or backup (False) the previous install directory with identical name or not. Default True'],
          'dontcreateinstalldir':[False,'Boolean to create (False) or not create (True) the install directory (Default False)'],
          'toolkit':[None, 'Name and version of toolkit'],
          'toolkitopts':['','Extra options for compilers'],
          'keepsymlinks':[False,'Boolean to determine whether symlinks are to be kept during copying or if the content of the files pointed to should be copied'],
          'licenseServer':[None,'License server for software'],
          'licenseServerPort':[None,'Port for license server'],
          'key':[None,'Key for installing software'],
          'pkglist':[[],'List with packages added to the baseinstallation (Default: [])'],
          'pkgmodulenames':[{},'Dictionary with real modules names for packages, if they are different from the package name (Default: {})'],
          'pkgloadmodule':[True,'Load the to-be installed software using temporary module (Default: True)'],
          'pkgtemplate':["%s-%s.tar.gz","Template for package source file names (Default: %s-%s.tar.gz)"],
          'pkgfindsource':[True,"Find sources for packages (Default: True)"],
          'pkginstalldeps':[True,"Install dependencies for specified packages if necessary (Default: True)"],
          'pkgdefaultclass':[None,"List of module for and name of the default package class (Default: None)"],
          'skip':[False,"Skip existing software (Default: False)"],
          'pkgfilter':[None,"Package filter details. List with template for cmd and input to cmd (templates for name, version and src). (Default: None)"],
          'pkgpatches':[[],'List with patches for packages (default: [])'],
          'pkgcfgs':[{},'Dictionary with config parameters for packages (default: {})'],
          'dependencies':[[],"List of dependencies (default: [])"],
          'builddependencies':[[],"List of build dependencies (default: [])"],
          'unpackOptions':[None,"Extra options for unpacking source (default: None)"],
          'modextravars':[{},"Extra environment variables to be added to module file (default: {})"],
          'osdependencies':[[], "Packages that should be present on the system"],
          'sources': [[], "List of source-items"],
          'patches': [[], "List of patches to apply"],
          'tests': [[], "List of test-scripts to run after install. A test script should return a non-zero exit status to fail"],
          'sanityCheckPaths': [{}, "List of files and directories to check (format: {'files':<list>, 'dirs':<list>}, default: {})"]
        }

        # module generator
        self.moduleGenerator = None

        # extra stuff for module file required by packages
        self.moduleExtraPackages=''

        self.pkgs = None
        self.skip = None

        self.sanityCheckPaths = None
        self.sanityCheckOK = True

        self.build_in_installdir = False

        if name and version:
            self.set_name_version(name, version, newBuild)
    
    def autobuild(self, ebfile, runTests):
        """
        Build the software package described by cfg.
        """
        self.process_ebfile(ebfile)

        if self.getcfg('stop') and self.getcfg('stop') == 'cfg':
            return True        
        self.log.info('Read specification file %s' % ebfile)

        self.ready2build()
        self.build()

        # Last stop
        if self.getcfg('stop'):
            return True
        self.make_module()

        # Run tests
        if runTests and self.getcfg('tests'):
            self.runtests()
        else:
            self.log.debug("Skipping tests")
                            
        return True
    
    def set_name_version(self,name,version,newBuild=True):
        """
        Sets name and version
        - also starts logger
        """
        self.setcfg('name', name)
        self.setcfg('version', version)
        if newBuild:
            self.setlogger()

    def setlogger(self):
        """
        Set the logger.
        """
        if not self.log:
            self.logfile, self.log, self.loghandler = initLogger(self.name(), self.version(),
                                                                 self.logdebug, typ=self.__class__.__name__)
            self.log.info("Init completed for application name %s version %s"%(self.name(),self.version())) 

    def closelog(self):
        """
        Shutdown the logger.
        """
        self.log.info("Closing log for application name %s version %s"%(self.name(),self.version()))
        removeLogHandler(self.loghandler)    
        self.loghandler.close()

    ## PARALLELISM
    def setparallelism(self,nr=None):
        """
        Determines how many processes should be used (default: nr of procs - 1).
        """
        if not nr and self.getcfg('parallel'):
            nr=self.getcfg('parallel')
        
        if nr:
            try:
                nr=int(nr)
            except ValueError,err:
                self.log.error("Parallelism %s not integer: %s"%(nr,err))
        else:
            # TODO: move out of Application, doesn't work on OS X
            # should go to tools/systemTools.py (refs #)
            nr=len([x for x in open('/proc/cpuinfo').readlines() if x.find("processor\t:") > -1])-1
            ## check ulimit -u
            out,ec=run_cmd('ulimit -u')
            try:
                if out.startswith("unlimited"):
                    out = 2^32-1
                maxuserproc=int(out)
                ## assume 6 proc per buildthread + 15 overhead
                maxnr=int((maxuserproc -15)/6)
                if maxnr < nr:
                    nr=maxnr
                    self.log.info("Limit parallel builds to %s because max user processes is %s"%(nr,out))
            except ValueError,err:
                self.log.exception("Failed to determine max user processes (%s,%s): %s"%(ec,out,err))

        self.setcfg('parallel', nr)
        self.log.info("Setting parallelism: %s"%nr)

    def addpatch(self,listOfPatches=None):
        """
        Add a list of patches.
        All patches will be checked if a file exists (or can be located)
        """
        if listOfPatches:
            for patchFile in listOfPatches:
                
                ## check if the patches can be located
                suff=None
                level=None
                if type(patchFile) == list:
                    if not len(patchFile) == 2:
                        self.log.error("Unknown patch specification '%s', only two-element lists are supported!"%patchFile)
                    pf=patchFile[0]
                    
                    if type(patchFile[1]) == int:
                        level=patchFile[1]
                    elif type(patchFile[1]) == str:
                        suff=patchFile[1]
                    else:
                        self.log.error("Wrong patch specification '%s', only int and string are supported as second element!"%patchFile)
                else:
                    pf=patchFile
                    
                path=self.file_locate(pf)
                if path:
                    self.log.debug('File %s found for patch %s'%(path,patchFile))
                    tmppatch={'name':pf,'path':path}
                    if suff:
                        tmppatch['copy']=suff
                    if level:
                        tmppatch['level']=level
                    self.patches.append(tmppatch)
                else:
                    self.log.error('No file found for patch %s'%patchFile)
            
            self.log.info("Added patches: %s"%self.patches)

    
    def addsource(self,listOfSources=None):
        """
        Add a list of source files (can be tarballs, isos, urls).
        All source files will be checked if a file exists (or can be located)
        """
        if listOfSources:
            for source in listOfSources:
                ## check if the sources can be located
                path=self.file_locate(source)
                if path:
                    self.log.debug('File %s found for source %s'%(path,source))
                    self.src.append({'name':source,'path':path})
                else:
                    self.log.error('No file found for source %s'%source)
                
            self.log.info("Added sources: %s"%self.src)

    def settoolkit(self, name, version):
        """
        Add the build toolkit to be used.
        """
        self.tk = Toolkit(name, version)
        self.log.info("Added toolkit: name %s version %s"%(self.tk.name,self.tk.version))

    def add_dependency(self, dependencies=None):
        """
        Add application dependencies. A dependency should be specified as a dictionary
        or as a list of the following form: [name, version, suffix, dummy_boolean]
        (suffix and dummy_boolean are optional)
        """
        if dependencies and len(dependencies) > 0:
            self.log.info("Adding dependencies: %s" % dependencies)
            self.dep.extend([self.parse_dependency(d) for d in dependencies])

    def parse_dependency(self, dep):
        """
        Read a dependency declaration and transform it to a common format.
        """
        result = {'name': '', 'version': '', 'prefix': '', 'suffix': ''}

        if type(dep) == dict:
            ## check for name and version key
            if not dep.has_key('name'):
                self.log.error('Dependency without name.')
                return
            result.update(dep)
        elif type(dep) in [list, tuple]:
            result['name'] = dep[0]
            if len(dep) >= 2:
                result['version'] = dep[1]
            if len(dep) >= 3:
                result['suffix'] = dep[2]
            if len(dep) >= 4:
                result['dummy'] = dep[3]
        else:
            self.log.error('Dependency %s from unsupported type: %s.'%(dep,type(dep)))
            return

        if not result.has_key('version'):
            self.log.warning('Dependency without version.')
    
        if not result.has_key('tk'):
            result['tk'] = self.tk.getDependencyVersion(result)

        return result
    
    ## process EasyBuild spec file 
    
    def process_ebfile(self,fn):
        """
        Read file fn, eval and add info
        - assume certain predefined variable names
        """
        if not os.path.isfile(fn) and self.log:
            self.log.error("Can't import config from unknown filename %s"%fn)

        try:
            locs = {"self": self}
            execfile(fn, {}, locs)
        except (IOError, SyntaxError), err:
            msg="Parsing cfg file %s failed"%(fn)
            if self.log:
                self.log.exception(msg)
            else:
                raise EasyBuildError("%s: %s"%(msg,err))
        
        ## initialize logger
        if locs.has_key('name') and locs.has_key('version'):
            self.set_name_version(locs['name'], locs['version'])
        else:
            self.setlogger()
        
        ## check EasyBuild version
        easybuildVersion = locs.get('easybuildVersion', None)
        if not easybuildVersion:
            self.log.warn("Specification-file does not specify an EasyBuild-version (key 'easybuildVersion')! Assuming the latest version")
        else:
            if LooseVersion(easybuildVersion) < easybuild.VERSION:
                self.log.warn("EasyBuild-version %s is older than the currently running one. Proceed with caution!" % easybuildVersion)
            elif LooseVersion(easybuildVersion) > easybuild.VERSION:
                self.log.error("EasyBuild-version %s is newer than the currently running one. Aborting!" % easybuildVersion)

        ## check for typos in eb file
        from difflib import get_close_matches
        for variable in locs.keys():
            guess = get_close_matches(variable,self.cfg.keys(),1,0.85)
            if len(guess) == 1 and variable not in self.cfg.keys():
                # We might have a typo here
                self.log.error("Don't you mean '%s' instead of '%s' as eb file variable."%(guess[0],variable))

        for k in self.cfg.keys():
            if locs.has_key(k):
                self.setcfg(k, locs[k])
                self.log.info("Using cfg option %s: value %s"%(k,self.getcfg(k)))

        for k in self.mandatory:
            if not locs.has_key(k):
                self.log.error("No cfg option %s provided"%k)
                
        if self.getcfg('stop') and not (self.getcfg('stop') in self.validstops):
            self.log.error("Stop provided %s is not valid: %s"%(self.cfg['stop'],self.validstops))

        if not (self.getcfg('moduleclass') in self.validmoduleclasses):
            self.log.error("Moduleclass provided %s is not valid: %s"%(self.cfg['moduleclass'],self.validmoduleclasses))                

        if self.getcfg('stop') == 'cfg':
            self.log.info("Stopping in parsing cfg")
            return

        if self.getcfg('osdependencies'):
            self.check_osdeps(self.getcfg('osdependencies'))
        
        if self.getcfg('sources'):
            self.addsource(self.getcfg('sources'))
        else:
            self.log.info('no sources provided')

        if self.getcfg('patches'):
            self.addpatch(self.getcfg('patches'))
        else:
            self.log.info('no patches provided')
        
        if self.getcfg('toolkit'):
            self.log.debug("toolkit: %s" % self.getcfg('toolkit'))
            tk = self.getcfg('toolkit')
            self.settoolkit(tk['name'], tk['version'])
        else:
            self.log.error('no toolkit defined')
        
        if self.getcfg('toolkitopts'):
            self.tk.setOptions(self.getcfg('toolkitopts'))
        
        if self.getcfg('dependencies'):
            self.add_dependency(self.getcfg('dependencies'))
        else:
            self.log.info('no dependencies provided')
            
        # Build dependencies
        builddeps = [self.parse_dependency(d) for d in self.getcfg('builddependencies')]
        self.add_dependency(builddeps)
        self.setcfg('builddependencies', builddeps)

        self.setparallelism()
        
        self.make_installversion()

        if hasattr(self, 'extracfg') or hasattr(self, 'extraCfg'):
            self.log.error("extracfg is deprecated, please extend self.cfg in __init__")
            self.extracfg(locs)
    
    def getcfg(self, key):
        """
        Get a configuration item.
        """
        return self.cfg[key][0]

    def setcfg(self, key, value):
        """
        Set configuration key to value.
        """
        self.cfg[key][0] = value

    def check_osdeps(self, osdeps):
        """
        Check if packages are available from OS. osdeps should be a list of dependencies.
        If an element of osdeps is a list, checks will pass if one of the elements of the list is found
        """
        for check in osdeps:
            if type(check) != list:
                check = [check]

            # find at least one element of check
            # - using rpm -q for now --> can be run as non-root!!
            # - should be extended to files later?
            found=False
            for d in check:
                cmd="rpm -q %s"%d
                res=run_cmd(cmd,simple=True)
                if res:
                    found = res
                    ## why continue?
                    break
            
            if not found:
                ## why continue?
                self.log.error("Couldn't verify any OS dependency for check %s as part of total osdeps %s"%(check,osdeps))
        
        self.log.info("OS dependencies ok: %s"%osdeps)
    
    ## BUILD 

    def ready2build(self):
        """
        Verify if all is ok to start build.
        """
        # Do all dependencies have a toolkit version
        self.tk.addDependency(self.dep)
        if not len(self.dep) == len(self.tk.dependencies):
            self.log.debug("dep %s (%s)\ntk.dep %s (%s)"%(len(self.dep),self.dep,len(self.tk.dependencies),self.tk.dependencies))
            self.log.error('Not all dependencies have a matching toolkit version')

        # Check if the application is not loaded at the moment
        envName = "SOFTROOT%s" % convertName(self.name(), upper = True)
        if os.environ.has_key(envName):
            self.log.error("Module is already loaded (%s is set), installation cannot continue." % envName)
        
        # Check if main install needs to be skipped
        # - if a current module can be found, skip is ok
        # -- this is potentially very dangerous
        if self.getcfg('skip'):
            if Modules().exists(self.name(), self.installversion):
                self.skip=True
                self.log.info("Current version (name: %s, version: %s) found. Going to skip actually main build and potential exitsing packages. Expert only."%(self.name(),self.installversion))
            else:
                self.log.info("No current version (name: %s, version: %s) found. Not skipping anything."%(self.name(),self.installversion))

        
    def file_locate(self,url,pkg=False):
        """
        Locates the file from url for this application
        - use predefined directories
        - homepage, urls, svn ...
        """
        srcPath = sourcePath()
        if type(srcPath) == list:
            for sp in srcPath:
                if pkg:
                    localdir=os.path.join(sp,self.name(),"packages")
                else:
                    localdir=os.path.join(sp,self.name())
                if os.path.isdir(localdir):
                    self.log.info("Source directory %s found!"%localdir)
                    break
        else:
            if pkg:
                localdir=os.path.join(srcPath,self.name(),"packages")
            else:
                localdir=os.path.join(srcPath,self.name())
        
        if url.find("http://") == 0:
            import urllib
            
            # if last source path tried doesn't exist, create it for downloading the source
            if not os.path.isdir(localdir):
                try:
                    os.makedirs(localdir)
                except OSError,err:
                    self.log.exception("Can't create directory %s: %s"%(localdir,err))
            try:
                webFile = urllib.urlopen(url)
                localfile = os.path.join(localdir,url.split('/')[-1])
                lf=open(localfile, 'w')
                lf.write(webFile.read())
                webFile.close()
                lf.close()
                self.log.debug("Downloading file %s from url %s ok"%(localfile,url))
            except IOError,err:
                self.log.exception("Downloading file %s from url %s failed: %s"%(localfile,url,err))
        else:
            localfile=os.path.join(localdir,url)
            
        if os.path.isfile(localfile):
            return localfile
        else:
            self.log.error("Local file %s from url %s not found"%(url,localfile))

    def apply_patch(self,beginpath=None):
        """
        Apply the patches
        """
        for tmp in self.patches:
            self.log.info("Applying patch %s"%tmp['name'])
            
            copy=False
            ## default: patch first source
            srcind=0
            if tmp.has_key('source'):
                srcind=tmp['source']
            srcpathsuffix=''
            if tmp.has_key('sourcepath'):
                srcpathsuffix=tmp['sourcepath']
            elif tmp.has_key('copy'):
                srcpathsuffix=tmp['copy']
                copy=True
            
            if not beginpath:
                beginpath=self.src[srcind]['finalpath']
            
            src=os.path.abspath("%s/%s"%(beginpath,srcpathsuffix))
            
            level=None
            if tmp.has_key('level'):
                level=tmp['level']
                
            if not patch(tmp['path'],src,copy=copy,level=level):
                self.log.error("Applying patch %s failed"%tmp['name'])

    def unpack_src(self):
        """
        Unpack the source files.
        """
        for tmp in self.src:
            self.log.info("Unpacking source %s"%tmp['name'])
            srcdir=unpack(tmp['path'],self.builddir,extraOptions=self.getcfg('unpackOptions'))
            if srcdir:
                self.src[self.src.index(tmp)]['finalpath']=srcdir
            else:
                self.log.error("Unpacking source %s failed"%tmp['name'])
  
    def build(self):
        """
        Build software
        - make builddir
        - generate install location name
        - unpack sources
        - patch sources
        - prepare dependencies
        - prepare toolkit
        - configure
        - make (use parallelism?)
        - test
        - make install location
        - install
        """
        try:
            print "preparing..."

            self.gen_installdir()
            self.make_builddir()

            ## SOURCE
            print "unpacking..."
            self.runstep('source', [self.unpack_src], skippable=True)

            ## PATCH
            self.runstep('patch', [self.apply_patch], skippable=True)

            self.tk.prepare(self.getcfg('onlytkmod'))
            self.startfrom()

            ## CONFIGURE
            print "configuring..."
            self.runstep('configure', [self.configure], skippable=True)

            ## MAKE
            print "building..."
            self.runstep('make', [self.make], skippable=True)

            ## TEST
            self.runstep('test', [self.test], skippable=True)

            ## INSTALL
            print "installing..."
            self.runstep('install', [self.make_installdir, self.make_install], skippable=True)

            ## Packages
            self.runstep('packages', [self.packages])

            print "finishing up..."

            ## POSTPROC
            self.runstep('postproc', [self.postproc], skippable=True)

            ## CLEANUP
            self.runstep('cleanup', [self.cleanup])
            
            ## SANITY CHECK
            self.runstep('sanity check', [self.sanitycheck], skippable=False)

        except StopException:
            pass

    def runstep(self, step, methods, skippable=False):
        """
        Run step, returns false when execution should be stopped
        """
        if skippable and self.skip:
            self.log.info("Skipping %s" % step)
        else:
            for m in methods:
                m()

        if self.getcfg('stop') == step:
            self.log.info("Stopping after %s step." % step)
            raise StopException(step)

    def postproc(self):
        """
        Do some postprocessing
        - set file permissions ....
        Installing user must be member of the group that it is changed to
        """
        if self.getcfg('group'):
            import grp
            gid=grp.getgrnam(self.getcfg('group'))[2]
            chngsuccess=[]
            chngfailure=[]
            for root, _, files in os.walk(self.installdir):
                try:
                    os.chown(root, -1, gid)
                    os.chmod(root, 0750)
                    chngsuccess.append(root)
                except OSError,err:
                    self.log.error("Failed to change group for %s: %s"%(root,err))
                    chngfailure.append(root)
                for f in files:
                    absfile = os.path.join(root, f)
                    try:
                        os.chown(absfile, -1, gid)
                        os.chmod(root, 0750)
                        chngsuccess.append(absfile)
                    except OSError,err:
                        self.log.debug("Failed to chown/chmod %s (but ignoring it): %s"%(absfile,err))
                        chngfailure.append(absfile)

            if len(chngfailure) > 0:
                self.log.error("Unable to change group permissions of file(s). Are you a member of this group?:\n --> %s"%"\n --> ".join(chngfailure))
            else:
                self.log.info("Successfully made software only available for group %s"%self.getcfg('group'))

    def cleanup(self):
        """
        Cleanup leftover mess
        - move log file
        - remove/clean build directory
        
        except when we're building in the installation directory, 
        otherwise we remove the installation
        """
        if not self.build_in_installdir:
            try:
                shutil.rmtree(self.builddir)
                self.log.info("Cleaning up builddir %s"%(self.builddir))
            except OSError,err:
                self.log.exception("Cleaning up builddir %s failed: %s"%(self.builddir,err))

    def sanitycheck(self):
        """
        Do a sanity check on the installation
        - if *any* of the files/subdirectories in the installation directory listed 
          in sanityCheckPaths are non-existent (or empty), the sanity check fails
        """
        # prepare sanity check paths
        self.sanityCheckPaths=self.getcfg('sanityCheckPaths')
        if not self.sanityCheckPaths:
            self.sanityCheckPaths={'files':[],
                                   'dirs':["bin","lib"]
                                   }
            self.log.info("Using default sanity check paths: %s"%self.sanityCheckPaths)
        else:
            ks=self.sanityCheckPaths.keys()
            ks.sort()
            valnottypes=[type(x) != list for x in self.sanityCheckPaths.values()]
            lenvals=[len(x) for x in self.sanityCheckPaths.values()]
            if not ks == ["dirs","files"] or sum(valnottypes) > 0 or sum(lenvals) == 0:
                self.log.error("Incorrect format for sanityCheckPaths (should only have 'files' and 'dirs' keys, values should be lists (at least one non-empty)).")

            self.log.info("Using customized sanity check paths: %s"%self.sanityCheckPaths)

        self.sanityCheckOK=True

        # check is files exist
        for f in self.sanityCheckPaths['files']:
            p=os.path.join(self.installdir,f)
            if not os.path.exists(p):
                self.log.debug("Sanity check: did not find file %s in %s"%(f,self.installdir))
                self.sanityCheckOK=False
                break
            else:
                self.log.debug("Sanity check: found file %s in %s"%(f,self.installdir))

        if self.sanityCheckOK:
            # check if directories exist, and whether they are non-empty     
            for d in self.sanityCheckPaths['dirs']:
                p=os.path.join(self.installdir,d)
                if not os.path.isdir(p) or not os.listdir(p):
                    self.log.debug("Sanity check: did not find non-empty directory %s in %s"%(d,self.installdir))
                    self.sanityCheckOK=False
                    break
                else:
                    self.log.debug("Sanity check: found non-empty directory %s in %s"%(d,self.installdir))

        # pass or fail
        if not self.sanityCheckOK:
            self.log.error("Sanity check failed!")
        else:
            self.log.debug("Sanity check passed!")


    def startfrom(self):
        """
        Return the directory where to start the whole configure/make/make install cycle from
        - typically self.src[0]['finalpath']
        - startfrom option
        -- if abspath: use that
        -- else, treat it as subdir for regular procedure
        """
        tmpdir=''
        if self.getcfg('startfrom'):
            tmpdir=self.getcfg('startfrom')

        if not os.path.isabs(tmpdir):
            if len(self.src) > 0 and not self.skip:
                self.setcfg('startfrom', os.path.join(self.src[0]['finalpath'],tmpdir))
            else:
                self.setcfg('startfrom', os.path.join(self.builddir,tmpdir))
        
        try:
            os.chdir(self.getcfg('startfrom'))
            self.log.debug("Changed to real build directory %s"%(self.getcfg('startfrom')))
        except OSError,err:
            self.log.exception("Can't change to real build directory %s: %s"%(self.getcfg('startfrom'),err))

    def configure(self):
        """
        Configure step
        - typically ./configure --prefix=/install/path style
        """
        cmd = "%s ./configure --prefix=%s %s" % (self.getcfg('preconfigopts'),self.installdir,self.getcfg('configopts'))
        run_cmd(cmd, log_all=True, simple=True)

    def make(self):
        """
        Start the actual build
        - typical: make -j X
        """
        paracmd=''
        if self.getcfg('parallel'):
            paracmd="-j %s" % self.getcfg('parallel')

        cmd = "%s make %s %s" % (self.getcfg('premakeopts'), paracmd, self.getcfg('makeopts'))

        run_cmd(cmd, log_all=True, simple=True)

    def test(self):
        """
        Test the compilation
        - default: None
        """
        if self.getcfg('runtest'):
            cmd = "make %s" % (self.getcfg('runtest'))
            run_cmd(cmd, log_all=True, simple=True)

    def make_install(self):
        """
        Create the installation in correct location
        - typical: make install
        """
        cmd = "make install %s" % (self.getcfg('installopts'))
        run_cmd(cmd, log_all=True, simple=True)

    def make_builddir(self):
        """
        Create the build directory.
        """
        if not self.build_in_installdir:
            # make a unique build dir
            ## if a tookitversion starts with a -, remove the - so prevent a -- in the path name 
            tkversion=self.tk.version
            if tkversion.startswith('-'):
                tkversion=tkversion[1:]
            
            extra="%s%s-%s%s"%(self.getcfg('versionprefix'),self.tk.name,tkversion,self.getcfg('versionsuffix'))
            localdir=os.path.join(buildPath(),self.name(),self.version(),extra)
            if not self.tk.name == 'dummy':
                localdir=os.path.join(localdir,extra)
    
            ald=os.path.abspath(localdir)
            tmpald=ald
            counter=1
            while os.path.isdir(tmpald):
                counter+=1
                tmpald="%s.%d"%(ald,counter)
            
            self.builddir=ald
    
            self.log.debug("Creating the build directory %s (cleanup: %s)"%(self.builddir,self.getcfg('cleanupoldbuild')))
        
        else:
            self.log.info("Changing build dir to %s"%self.installdir)
            self.builddir=self.installdir

            self.log.info("Overriding 'cleanupoldinstall' (to False), 'cleanupoldbuild' (to True) " \
                          "and 'keeppreviousinstall' because we're building in the installation directory.")
            # force cleanup before installation
            self.setcfg('cleanupoldbuild',True)
            self.setcfg('keeppreviousinstall',False)
            # avoid cleanup after installation
            self.setcfg('cleanupoldinstall',False)
            
        # always make build dir
        self.make_dir(self.builddir,self.getcfg('cleanupoldbuild'))
    
    def gen_installdir(self):
        """
        Generate the name of the installation directory.
        """
        basepath=installPath()
        
        if basepath:
            installdir=os.path.join(basepath,self.name(),self.installversion)
            self.installdir=os.path.abspath(installdir)
        else:
            self.log.error("Can't set installation directory")
    
    def make_installversion(self):
        """
        Generate the installation version name.
        """
        vpf, vsf = self.getcfg('versionprefix'), self.getcfg('versionsuffix')

        if self.tk.name == 'dummy':
            name = "%s%s%s" % (vpf, self.version(), vsf)
        else:
            extra = "%s-%s" % (self.tk.name, self.tk.version)
            name = "%s%s-%s%s"% (vpf, self.version(), extra, vsf)
        
        self.installversion = name
        
    def make_installdir(self):
        """
        Create the installation directory.
        """
        self.log.debug("Creating the installation directory %s (cleanup: %s)"%(self.installdir,self.getcfg('cleanupoldinstall')))
        if self.build_in_installdir:
            self.setcfg('keeppreviousinstall',True)
        self.make_dir(self.installdir,self.getcfg('cleanupoldinstall'),self.getcfg('dontcreateinstalldir'))
    
    def make_dir(self,dirName,clean,dontcreateinstalldir=False):
        """
        Create the directory.
        """
        if os.path.exists(dirName):
            self.log.info("Found old directory %s"%dirName)
            if self.getcfg('keeppreviousinstall'):
                self.log.info("Keeping old directory %s (hopefully you know what you are doing)"%dirName)
                return 
            elif clean:
                try:
                    shutil.rmtree(dirName)
                    self.log.info("Removed old directory %s"%dirName)
                except OSError,err:
                    self.log.exception("Removal of old directory %s failed: %s"%(dirName,err))
            else:
                try:
                    timestamp = time.strftime("%Y%m%d-%H%M%S")
                    backupdir = "%s.%s"%(dirName,timestamp)
                    shutil.move(dirName, backupdir)
                    self.log.info("Moved old directory %s to %s" % (dirName,backupdir))
                except OSError,err:
                    self.log.exception("Moving old directory to backup %s %s failed: %s" % (dirName,backupdir,err))

        if dontcreateinstalldir:
            olddir=dirName
            dirName=os.path.dirname(dirName)
            self.log.info("Cleaning only, no actual creation of %s, only verification/creation of dirname %s"%(olddir,dirName))
            if os.path.exists(dirName):
                return 
            ## if not, create dir as usual

        try:
            os.makedirs(dirName)
        except OSError,err:
            self.log.exception("Can't create directory %s: %s"%(dirName,err))

    def make_module(self, fake = False):
        """
        Generate a module file.
        """
        self.moduleGenerator = ModuleGenerator(self, fake)
        self.moduleGenerator.createFiles()

        txt = ''
        txt += self.make_module_description()
        txt += self.make_module_dep()
        txt += self.make_module_req()
        txt += self.make_module_extra()
        if self.getcfg('pkglist'):
            txt += self.make_module_extra_packages()

        try:
            f = open(self.moduleGenerator.filename, 'w')
            f.write(txt)
            f.close()
        except IOError,err:
            self.log.error("Writing to the file %s failed: %s" % (self.moduleGenerator.filename, err))

        self.log.info("Added modulefile: %s" % (self.moduleGenerator.filename))
    
    def make_module_description(self):
        """
        Create the module description.
        """
        return self.moduleGenerator.getDescription()

    def make_module_dep(self):
        """
        Make the dependencies for the module file.
        """
        load = unload = ''
        
        # Load toolkit
        if self.tk.name != 'dummy':
            load += self.moduleGenerator.loadModule(self.tk.name, self.tk.version)
            unload += self.moduleGenerator.unloadModule(self.tk.name, self.tk.version)
        
        # Load dependencies
        builddeps = self.getcfg('builddependencies')
        for dep in self.tk.dependencies:
            if not dep in builddeps:
                self.log.debug("Adding %s/%s as a module dependency" % (dep['name'], dep['tk']))
                load += self.moduleGenerator.loadModule(dep['name'], dep['tk'])
                unload += self.moduleGenerator.unloadModule(dep['name'], dep['tk'])
            else:
                self.log.debug("Skipping builddependency %s/%s" % (dep['name'], dep['tk']))
        
        # Force unloading any other modules
        if self.getcfg('moduleforceunload'):
            return unload + load
        else:
            return load
        
    def make_module_req(self):
        """
        Generate the environment-variables to run the module.
        """
        requirements = self.make_module_req_guess()

        txt = "\n"
        for key in sorted(requirements):
            for path in requirements[key]:
                globbedPaths = glob.glob(os.path.join(self.installdir, path))
                txt += self.moduleGenerator.prependPaths(key, globbedPaths)
        return txt

    def make_module_req_guess(self):
        """
        A dictionary of possible directories to look for.
        """
        return {
            'PATH': ['bin'],
            'LD_LIBRARY_PATH': ['lib','lib64'],
            'MANPATH': ['man','share/man']
        }

    def make_module_extra(self):
        """
        Sets optional variables (SOFTROOT, MPI tuning variables).
        """
        txt = "\n"

        if hasattr(self, 'makeModuleExtraExtra') or hasattr(self, 'make_module_extra_extra'):
            self.log.error("make_module_extra_extra is deprecated, please override makeModuleExtra" \
                          "and append to the parent result.")
            txt += self.make_module_extra_extra() + "\n"

        ## SOFTROOT + SOFTVERSION
        environmentName = convertName(self.name(), upper=True)
        txt += self.moduleGenerator.setEnvironment("SOFTROOT" + environmentName, "$root")
        txt += self.moduleGenerator.setEnvironment("SOFTVERSION" + environmentName, self.version())
        
        txt += "\n"
        for key, value in self.getcfg('modextravars').items():
            txt += self.moduleGenerator.setEnvironment(key, value)
      
        self.log.debug("makeModuleExtra added this: %s"%txt)
 
        return txt
    
    def make_module_extra_packages(self):
        """
        Sets optional variables for packages.
        """
        return self.moduleExtraPackages

    def packages(self):
        """
        After make install, run this.
        - only if variable len(pkglist) > 0 
        - optionally: load module that was just created using temp module file
        - find source for packages, in pkgs
        - run extraPackages
        """
        
        if len(self.getcfg('pkglist')) == 0:
            self.log.debug("No packages in pkglist")
            return

        if not self.skip:
            self.make_module(fake=True)
        # set MODULEPATH to self.builddir/all and load module
        if self.getcfg('pkgloadmodule'):
            self.log.debug(' '.join(["self.builddir/all: ",os.path.join(self.builddir,'all')]))
            if self.skip:
                m=Modules()
            else:
                m=Modules([os.path.join(self.builddir,'all')]+os.environ['MODULEPATH'].split(':'))
                
            if m.exists(self.name(),self.installversion):
                m.addModule([[self.name(),self.installversion]])
                m.load()
            else:
                self.log.error("module %s version %s doesn't exist"%(self.name(),self.installversion))

        self.extra_packages_pre()

        self.pkgs=self.find_package_sources()

        if self.skip:
            self.filter_packages()

        self.extra_packages()

    def find_package_patches(self,pkgName):
        """
        Find patches for packages.
        """
        for (name,patches) in self.getcfg('pkgpatches'):
            if name == pkgName:
                pkgpatches=[]
                for p in patches:
                    pf=self.file_locate(p,pkg=True)
                    if pf:
                        pkgpatches.append(pf)
                    else:
                        self.log.error("Unable to locate file for patch %s."%p)
                return pkgpatches
        return []

    def find_package_sources(self):
        """
        Find source file for packages.
        """
        pkgSources=[]
        for pkg in self.getcfg('pkglist'):
            if type(pkg) in [list, tuple] and pkg:
                pkgName=pkg[0]
                forceunknownsource=False
                if len(pkg) == 1:
                    pkgSources.append({'name':pkgName})
                else:
                    if len(pkg) == 2:
                        fn=self.getcfg('pkgtemplate')%(pkgName,pkg[1])
                    elif len(pkg) == 3:
                        if type(pkg[2]) == bool:
                            forceunknownsource=pkg[2]
                        else:
                            fn=pkg[2]
                    else:
                        self.log.error('Package specified in unknown format (list/tuple too long)')

                    if forceunknownsource:
                        pkgSources.append({'name':pkgName,
                                           'version':pkg[1]})
                    else:
                        filename=self.file_locate(fn,True)
                        if filename:
                            pkgSrc={'name':pkgName,
                                    'version':pkg[1],
                                    'src':filename}
                                                
                            pkgPatches=self.find_package_patches(pkgName)
                            if pkgPatches:
                                self.log.debug('Found patches for package %s: %s'%(pkgName,pkgPatches))
                                pkgSrc.update({'patches':pkgPatches})
                            else:
                                self.log.debug('No patches found for package %s.'%pkgName)
                                
                            pkgSources.append(pkgSrc)
                            
                        else:
                            self.log.warning("Source for package %s not found.")
                            
            elif type(pkg) == str:
                pkgSources.append({'name':pkg})
            else:
                self.log.error("Package specified in unknown format (not a string/list/tuple)")

        return pkgSources
                              
    def extra_packages_pre(self):
        """
        Also do this before (eg to set the template)
        """

    def extra_packages(self):
        """
        Also do this (ie the real work)
        - based on original R version
        - it assumes a class that has a run function
        -- the class is instantiated and the at the end <instance>.run() is called
        -- has defaultclass
        """
        pkginstalldeps=self.getcfg('pkginstalldeps')
        self.log.debug("Installing packages")
        pkgdefaultclass=self.getcfg('pkgdefaultclass')
        if not pkgdefaultclass:
            self.log.error("ERROR: No default package class set for %s"%self.name())

        allclassmodule=pkgdefaultclass[0]
        defaultClass=pkgdefaultclass[1]
        for pkg in self.pkgs:
            name=pkg['name']
            self.log.debug("Starting package %s"%name)
            
            try:
                exec("from %s import %s"%(allclassmodule,name))
                p = eval("%s(self,pkg,pkginstalldeps)"%name)
                self.log.debug("Installing package %s through class %s"%(name,name))
            except (ImportError,NameError),err:
                self.log.debug("Couldn't load class %s for package %s with package deps %s:\n%s"%(name,name,pkginstalldeps,err))
                if defaultClass:
                    self.log.info("No class found for %s, using default %s instead."%(name,defaultClass))
                    try:
                        exec("from %s import %s"%(allclassmodule,defaultClass))
                        exec("p=%s(self,pkg,pkginstalldeps)"%defaultClass)
                        self.log.debug("Installing package %s through default class %s"%(name,defaultClass))
                    except (ImportError,NameError),errbis:
                        self.log.error("Failed to use both class %s and default %s for package %s, giving up:\n%s\n%s"%(name,defaultClass,name,err,errbis))
                else:
                    self.log.error("Failed to use both class %s and no default class for package %s, giving up:\n%s"%(name,name,err))

            ## real work
            p.prerun()
            txt=p.run()
            if txt:
                self.moduleExtraPackages+=txt
            p.postrun()

    def filter_packages(self):
        """
        Called when self.skip is True
        - use this to detect existing packages and to remove them from self.pkgs
        - based on initial R version 
        """
        cmdtmpl=self.getcfg('pkgfilter')[0]
        cmdinputtmpl=self.getcfg('pkgfilter')[1]
        
        res=[]
        for pkg in self.pkgs:
            name=pkg['name']
            if self.getcfg('pkgmodulenames').has_key(name):
                modname=self.getcfg('pkgmodulenames')[name]
            else:
                modname = name
            tmpldict={'name':modname,
                       'version':pkg.get('version'),
                       'src':pkg.get('source')
                       }
            cmd=cmdtmpl%tmpldict
            if cmdinputtmpl:
                stdin=cmdinputtmpl%tmpldict
                (cmdStdouterr,ec)=run_cmd(cmd,log_all=False,log_ok=False,simple=False,inp=stdin,regexp=False)
            else:
                (cmdStdouterr,ec)=run_cmd(cmd,log_all=False,log_ok=False,simple=False,regexp=False)
            if ec:
                self.log.info("Not skipping %s"%name)
                self.log.debug("exit code: %s, stdout/err: %s"%(ec,cmdStdouterr))
                res.append(pkg)
            else:
                self.log.info("Skipping %s"%name)
        self.pkgs=res
    
    def runtests(self):
        """
        Run tests.
        """
        for test in self.getcfg('tests'):
            # Current working dir no longer exists
            os.chdir(self.installdir)
            if os.path.isabs(test):
                path = test
            else:
                path = os.path.join(sourcePath(), self.name(), test)
            
            try:
                self.log.debug("Running test %s" % path)
                run_cmd(path, log_all=True, simple=True)
            except EasyBuildError,err:
                self.log.exception("Running test %s failed: %s"%(path,err))
    
    def name(self):
        """
        Shortcut the get the module name.
        """
        return self.getcfg('name')

    def version(self):
        """
        Shortcut the get the module version.
        """
        return self.getcfg('version')

    def dump_cfg_options(self):
        """
        Print a list of available configuration options.
        """
        for key in sorted(self.cfg):
            tabs = "\t" * (3 - (len(key) + 1)/8)
            print "%s:%s%s" % (key, tabs, self.cfg[key][1])

class StopException(Exception):
    """
    StopException class definition.
    """
    pass

def get_instance(applicationClass, log):
    """
    Get instance for a particular application class (or Application)
    """
    try:
        if not applicationClass:
            applicationClass = "framework.application.Application"
        (modulepath, module, className) = applicationClass.split('.')
        execstr="from easybuild.%s import %s" % (modulepath, module)
        log.debug(execstr)
        execstr
        return eval("%s()" % className)
    except (ImportError,NameError), err:
        log.exception("Can't process provided module and class pair %s" % (applicationClass))
        raise err

class ApplicationPackage:
    """
    Class for packages.
    """
    def __init__(self,mself,pkg,pkginstalldeps):
        """
        mself has the logger
        """
        self.master=mself
        self.log=self.master.log
        self.cfg=self.master.cfg
        self.pkg=pkg
        self.pkginstalldeps=pkginstalldeps
        
        if not self.pkg.has_key('name'):
            self.log.error("")
        
        self.name=self.pkg.get('name',None)
        self.version=self.pkg.get('version',None)
        self.src=self.pkg.get('src',None)
        self.patches=self.pkg.get('patches',None)

    def prerun(self):
        """
        Stuff to do before installing a package.
        """
        pass

    def run(self):
        """
        Actual installation of a package.
        """
        pass

    def postrun(self):
        """
        Stuff to do after installing a package.
        """
        pass