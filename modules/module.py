"""
This is the top level object that modules will inherit from.
"""
import hashlib
import os
import random
import re
import sys
import time

DEBUG = False

if os.name == 'posix' and sys.version_info[0] < 3:
    import subprocess32 as subprocess
else:
    import subprocess

try:
    input = raw_input
except NameError:
    pass

from shlex import split as shlexSplit
from shutil import copyfile, copytree, rmtree

DEFAULT_FILE_BLACKLIST = [
    '.*libreoffice.*',
]

def debug(msg):
    if DEBUG:
        print("DEBUG: {}".format(msg))

class Module (object):
    def __init__(self, title, prompt='Bootcamp > ', banner='Welcome to the Linux Bootcamp.\nInitializing your environment...', flag=None, binaries=None, blacklist=None, whitelist=None, timeout=10, uid=None, gid=None, file_blacklist=None):
        self.title = title
        self.prompt = prompt
        self.cur_prompt = '[~] {}'.format(prompt)
        self.history = []
        self.banner = banner
        self.flag = flag
        self.binaries = binaries if binaries is not None else []
        self.cmd_whitelist = whitelist if blacklist is not None else []
        self.cmd_blacklist = blacklist if blacklist is not None else []
        self.timeout = timeout
        self.uid = uid
        self.gid = gid
        self.file_blacklist=file_blacklist if file_blacklist is not None else DEFAULT_FILE_BLACKLIST

        self.real_root = None

        # Environment
        #self.env = os.environ.copy()
        self.env = {}

        # Directory Tracking
        self.env['HOME'] = '/home/root/'
        self.env['PWD'] = '/home/root/'
        self.env['OLDPWD'] = '/home/root/'
        self.env['TEMP'] = 'TEMP'

        # Temporary root, initialize should generate new one.
        self.root_dir = '/tmp/bootcamp/temp'

        self.check_err = "That's not quite right. Please try again.\n"

    """
    This function copies potential dependencies into the virtual environment.
    """
    def _copy_libraries(self, directory):
        for root, directories, files in os.walk(directory):
            for direct in directories:
                dirpath = os.path.join(root, direct)
                debug('mkdir {}'.format('{}{}'.format(self.root_dir, dirpath)))
                os.makedirs('{}{}'.format(self.root_dir, dirpath))

            for file in files:
                pathtofile = os.path.join(root, file)
                r = re.compile('.*\.so[\.0-9]*')
                matches = r.findall(pathtofile)
                if len(matches) < 1:
                    #debug("File blacklisted: {}".format(pathtofile))
                    continue
                if not self._blacklist_match(pathtofile):
                    debug('!!cp -f {} {}'.format(pathtofile, '{}{}'.format(self.root_dir, pathtofile)))
                    try:
			os.system('cp -f {} {} > /dev/null 2>&1'.format(pathtofile, '{}{}'.format(self.root_dir, pathtofile)))
			#copyfile(pathtofile, os.path.join(self.root_dir, pathtofile.lstrip('/')))
		    except Exception as e:
			debug(e)
    """
    This function can be used by subprocess to execute commands as a given uid and gid.
    """
    def _assume_id(self):

        uid = os.getuid()
        gid = os.getgid()

        if self.gid is not None:
            gid = self.gid
        if self.uid is not None:
            uid = self.uid

        def set_ids():
            # Configure UID and GID
            try:
                
		os.setregid(gid, gid)
                os.setgroups([gid])
		os.setreuid(uid, uid)
            except Exception as e:
                debug(e)

        return set_ids

    """
    This function compares a file name to a regex to see if it should be allowed into the environment.
    """
    def _blacklist_match(self, filename):
        for exp in self.file_blacklist:
            r = re.compile(exp)
            matches = r.findall(filename)
            if len(matches) > 0:
                debug("File blacklisted: {}".format(filename))
                return True
        return False

    """
    Initialize the environment for this module.
    If your module requires additional support, either override this method,
    or the `start` method (If you want to also include this functionality).
    """
    def initialize(self):
        # Clear the screen
        sys.stderr.write("\x1b[2J\x1b[H")

        # Print the banner
        print(self.banner)

        # Store root directory
        self.real_root = os.open("/", os.O_RDONLY)

        # Generate unique directory path
        md5_hash = hashlib.md5()
        md5_hash.update("{}{}{}".format(self.title, time.time(), random.randint(0, 429496729)).encode('utf-8'))
        self.root_dir = '/tmp/bootcamp/'+md5_hash.hexdigest()
        debug("Generated fake root: {}".format(self.root_dir))

        # Create the virtual env directory
        venv_dir = '{}{}'.format(self.root_dir, '/bin')
        if not os.path.exists(venv_dir):
            debug("Making binary directory {}".format(venv_dir))
            os.makedirs(venv_dir)

        # Copy module files into root directory
        mod_fileroot = os.path.join('files/', self.title)
        if os.path.exists(mod_fileroot):
            for f in os.listdir(mod_fileroot):
                debug("Copying module files")
                debug("cp -rf {} {}".format(os.path.abspath(os.path.join(mod_fileroot, f)), self.root_dir))
                os.system("cp -rf {} {}".format(os.path.abspath(os.path.join(mod_fileroot, f)), self.root_dir))

        # Create home directory
        home = '{}{}'.format(self.root_dir, self.env['HOME'])
        if not os.path.exists(home):
            debug("Making home directory {}".format(home))
            os.makedirs(home)

        # Copy sh
        if '/bin/sh' not in self.binaries:
            self.binaries.append('/bin/sh')

        # Copy bash
        if '/bin/bash' not in self.binaries:
            self.binaries.append('/bin/bash')

        self._copy_libraries('/usr/lib')
        self._copy_libraries('/lib')
        self._copy_libraries('/usr/lib64')
        self._copy_libraries('/lib64')

        # Copy binaries (and copy dependencies) into environment
        for binary in self.binaries:
            debug("Copying file/directory {}".format(binary))
            new_bin = self.root_dir+'/bin/'+os.path.basename(binary)
            copyfile(binary, new_bin)
            os.chmod(new_bin, 0555)
            #debug("ldd {} | egrep '(.dylib|.so)' | awk '{{ print $1 }}' | xargs -I@ bash -c 'sudo cp @ {}@'".format(binary, self.root_dir))
            #os.system("ldd {} | egrep '(.dylib|.so)' | awk '{{ print $1 }}' | xargs -I@ bash -c 'sudo cp @ {}@'".format(binary, self.root_dir))

        # Chroot into the virtual environment (This requires root access)
        os.chdir(self.root_dir)
        os.chroot(self.root_dir)
        os.chdir(self.env['HOME'])

        # Setup Environment Variables
        self.env['SHELL'] = '/bin/sh'
        self.env['PATH'] = '/bin'

    """
    This function is called to start the module.
    You may override this for a more custom experience.
    """
    def start(self):
        self.input_loop(self.parser_func)
        self.exit(False)
        print("Congratulations! You've completed {}\n".format(self.title))

    """
    Compares to see if the input matches the given command.
    If not, it will print the standard error message.
    """
    def check(self, cmd, program_input):
        if cmd == program_input:
            return True
        print(self.check_err)
        return False

    """
    Cleanup and then sys.exit. This should be overridden if special cleanup is necessary.
    """
    def exit(self, exit=True):
        print("Cleaning up...")
        # Exit the chroot environment
        os.fchdir(self.real_root)
        os.chroot(".")
        os.close(self.real_root)

        try:
            rmtree(self.root_dir)
        except Exception as e:
            # Couldn't cleanup properly, still exit though.
            debug(e)
        if exit:
            sys.exit('Exiting Bootcamp...')

    """
    This function is used to determine if we will allow the user input.
    """
    def validate_input(self, program_input):
        if program_input is not None and program_input != "":
            # Specifically allow cd, exit, clear, and pwd
            if program_input == 'cd' or program_input == 'exit' or program_input == 'clear' or program_input == 'pwd':
                return True

            # Check whitelist
            if self.cmd_whitelist is not None and self.cmd_whitelist != []:
                whitelist_matched = False
                for exp in self.cmd_whitelist:
                    r = re.compile(exp)
                    matches = r.findall(program_input)
                    if len(matches) > 0:
                        whitelist_matched = True
                        break
                if not whitelist_matched:
                    return False

            # Check blacklist
            if self.cmd_blacklist is not None and self.cmd_blacklist != []:
                blacklist_matched = False
                for exp in self.cmd_blacklist:
                    r = re.compile(exp)
                    matches = r.findall(program_input)
                    if len(matches) > 0:
                        blacklist_matched = True
                        break
                if blacklist_matched:
                    return False
        return True

    """
    Inheriting modules should override this function with their own logic.
    This function is used to determine if the input/output should complete the module.
    """
    def is_success(self, program_input, program_output):
        if self.flag is not None:
            return self.flag in program_input or self.flag in program_output
        return False

    """
    Execute a command within the virtual environment.
    """
    def safe_exec(self, program_input):
        # Simulate working directory
        if program_input.startswith('cd'):
            args = shlexSplit(program_input)
            if len(args) < 2 or args[1] == '~':
                self.env['OLDPWD'] = self.env['PWD']
                os.chdir(self.env['HOME'])
            elif args[1] == '-':
                tmp = self.env['OLDPWD']
                self.env['OLDPWD'] = self.env['PWD']
                os.chdir(tmp)
            else:
                self.env['OLDPWD'] = self.env['PWD']
                os.chdir(os.path.abspath(args[1]))

            self.env['PWD'] = os.getcwd()

            if self.env['PWD'].strip('/') == self.env['HOME'].strip('/'):
                self.cur_prompt = '[~] {}'.format(self.prompt)
            else:
                self.cur_prompt = '[{}] {}'.format(os.path.abspath(os.getcwd()), self.prompt)
            return ''
        elif program_input == 'pwd':
            return self.env['PWD']
        elif program_input == 'clear':
            sys.stderr.write("\x1b[2J\x1b[H")
            return ''

        # Execute Command
        cmd = " ".join(shlexSplit(program_input))
        program_output = subprocess.check_output(cmd,
            shell=True, env=self.env,
            timeout=self.timeout,
            preexec_fn=self._assume_id())
        self.history.append(program_input)
        return program_output

    """
    This is the default parser_func that is called by input_loop with program_input.
    By default, it look's for the exit command, if found it calls self.exit. Else,
    it will execute the given command in the virtual environment.
    """
    def parser_func(self, program_input):
        if program_input == 'exit':
            self.exit()

        program_output = self.safe_exec(program_input)

        print(program_output)

        return program_output

    """
    This function will loop, displaying the prompt and recieving input.
    Input received is sent to the given parser_func parameter.
    """
    def input_loop(self, parser_func):
        while True:
            try:
                # Retrieve Input
                program_input = input(self.cur_prompt)

                # Validate
                if not self.validate_input(program_input):
                    print("Error: Invalid input")
                    continue

                # Parse and execute
                if callable(parser_func):
                    program_output = parser_func(program_input)

                # Check for success
                if self.is_success(program_input, program_output):
                    break

            except Exception as e:
                debug(e)
                print("Error: Could not execute command")
