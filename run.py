""" Pieces of python code used by the runscript.sh

This includes in particular reading and writing namelist files

Usage:
    run.py [--glacier=<name>] [--years=<years>] [(--continue | --reset)] [--over] [--params=<params> [--write-params] ] [--exe=<main.exe>] [--dry-run]

Options:
    -h --help           Show this screen
    --glacier=<name>    glacier name
    --params=<params>   update glacier parameters
                        e.g. --params='{"submelt":{"cal_melt":100,"scal":1}}'
    -w --write-params   Make parameter changes persistent (always true for control)
    --years=<years>     Number of years of simulation
    --continue          Continue previous simulation (see below).
    --over              In continue mode, the over flag overwrite the output
    --reset             Restart from restart in input directory
    --exe=<main.exe>    Executable [default: ./main.exe ]
    --dry-run           Only update the namelists, do not execute the program

Continue a previous simulation with --continue:
    - Read restart from out directory
    - keep the same simulation length, but increment year0 and yearf 
    - Append to the output file (unless the --over flag is also set)
    to continue after the previous restart.
Otherwise keep the restart file as it was.
"""
import subprocess
from collections import OrderedDict
from namelist import read_namelist_file
import sys, os, docopt, json

NML_CONTROL = 'control.nml'
NML_DEFAULTS = 'params.nml'
NML_UPDATE = 'input/{glacier}/update.nml'
NML_GLACIER = 'input/{glacier}/input.nml'


#
# Here model-specific functions
#
def get_glacier_name():
    " get glacier name from control "
    control = read_namelist_file(NML_CONTROL)
    return control.groups['general']['name']
    

def get_checksum(codedir='./', safe=True):
    """ return git's checksum
    """
    cmd = 'cd {codedir} && git log | head -1 | sed "s/commit //"'.format(codedir=codedir)
    commit = subprocess.check_output(cmd, shell=True)

    if safe:
        cmd = 'cd {codedir} && git status | grep "Changes.*commit" \
            || dummy_command_to_avoid_error=1'.format(codedir=codedir)
        # cmd = 'cd {codedir} && echo $status | grep "Changes.*commit"'.format(codedir=codedir)
        changes = subprocess.check_output(cmd, shell=True)
        if changes != "":
            cmd = 'cd {codedir} && git status'.format(codedir=codedir)
            os.system(cmd)
            y = raw_input("git directory not clean, proceed? (press 'y') ")
            if y != 'y':
                print "Stopped by user."
                sys.exit()

    return commit


def main():
    args = docopt.docopt(__doc__)
    print args
    control = read_namelist_file(NML_CONTROL)

    # check the glacier name
    # if not provided, read in the control file
    if args['--glacier'] is None:
        glacier = control.groups['general']['name']
    # otherwise, just take from the command line
    else:
        glacier = args['--glacier']
        control.groups['general']['name'] = glacier

    #
    # update glacier parameters
    #
    nml_update = NML_UPDATE.format(glacier=glacier)
    nml_glacier = NML_GLACIER.format(glacier=glacier)

    params = read_namelist_file(NML_DEFAULTS) # default

    # glacier-specific parameters
    if os.path.isfile(nml_update):
        specific = read_namelist_file(nml_update) 
    else:
        specific = Namelist("")

    # update from command line parameters?
    if args['--params']:
        user=json.loads(args['--params'])
        print user
        for group in user.keys():
            if group not in specific.groups:
                specific.groups[group] = OrderedDict()
            specific.groups[group].update(user[group])

        # write user-input parameters to the glacier specifics?
        if args['--write-params']:
            with open(nml_update,'w') as f:
                f.write(specific.dump())

    # update defaults
    for group in specific.groups:
        params.groups[group].update(specific.groups[group])

    # write down the updated glacier namelist
    print "write namelist to",nml_glacier
    with open(nml_glacier,'w') as f:
        f.write(params.dump())

    #
    # update control namelist
    #

    # continue previous simulation?
    if args['--continue']:
        control.groups['general']['rst_dir'] = 'out'
        control.groups['output']['out_mode'] = 'append'
        # udpate simulation dates
        duration = control.groups['time']['yearf'] - control.groups['time']['year0'] + 1
        control.groups['time']['year0'] += duration
        control.groups['time']['yearf'] += duration

    # reset to restart present in input dir
    elif args['--reset']:
        control.groups['general']['rst_dir'] = 'input'
        control.groups['output']['out_mode'] = 'overwrite'
        duration = control.groups['time']['yearf'] - control.groups['time']['year0'] + 1
        control.groups['time']['year0'] = 0
        control.groups['time']['yearf'] = duration-1

    # overwrite the output (instead of append mode)
    if args['--over']:
        control.groups['output']['out_mode'] = 'overwrite'

    # number of years of simulation
    if args['--years']:
        control.groups['time']['yearf'] = control.groups['time']['year0'] + int(args['--years']) - 1

    # write the control file to disk
    print "write ",NML_CONTROL
    with open(NML_CONTROL,'w') as f:
        f.write(control.dump())

    if args['--dry-run']:
        # sys.exit()
        return

    if args['--exe']:
        executable = args['--exe']
    else:
        executable = args['--exe']
        #"./main.exe"

    # execute the fortran script
    os.system(executable)

if __name__ == "__main__":
    main()
