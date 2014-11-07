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
from collections import OrderedDict
import re
import sys, os, docopt, json

NML_CONTROL = 'control.nml'
NML_DEFAULTS = 'params.nml'
NML_UPDATE = 'input/{glacier}/update.nml'
NML_GLACIER = 'input/{glacier}/input.nml'


def read_namelist_file(filename):
    return Namelist(open(filename, 'r').read())

class AttributeMapper():
    """
    Simple mapper to access dictionary items as attributes
    """

    def __init__(self, obj):
        self.__dict__['data'] = obj

    def __getattr__(self, attr):
        if attr in self.data:
            found_attr = self.data[attr]
            if isinstance(found_attr, dict):
                return AttributeMapper(found_attr)
            else:
                return found_attr
        else:
            raise AttributeError

    def __setattr__(self, attr, value):
        if attr in self.data:
            self.data[attr] = value
        else:
            raise NotImplementedError

    def __dir__(self):
        return self.data.keys()

class Namelist():
    """
    Parses namelist files in Fortran 90 format, recognised groups are
    available through 'groups' attribute.
    """

    def __init__(self, input_str):
        self.groups = OrderedDict()

        group_re = re.compile(r'&([^&]+)/', re.DOTALL)  # allow blocks to span multiple lines
        array_re = re.compile(r'(\w+)\((\d+)\)')
        # string_re = re.compile(r"\'\s*\w[^']*\'")
        string_re = re.compile(r"[\'\"]*[\'\"]")
        self._complex_re = re.compile(r'^\((\d+.?\d*),(\d+.?\d*)\)$')

        # remove all comments, since they may have forward-slashes
        # TODO: store position of comments so that they can be re-inserted when
        # we eventually save
        filtered_lines = []
        for line in input_str.split('\n'):
            if '!' in line:
                line = line[:line.index('!')]
            if line.strip() == "":
                continue
            else:
                filtered_lines.append(line)

        group_blocks = re.findall(group_re, "\n".join(filtered_lines))

        for i, group_block in enumerate(group_blocks):
            block_lines = group_block.split('\n')
            group_name = block_lines.pop(0).strip()

            group = OrderedDict()

            for line in block_lines:
                line = line.strip()
                if line == "":
                    continue
                if line.startswith('!'):
                    continue

                # commas at the end of lines seem to be optional
                if line.endswith(','):
                    line = line[:-1]

                k, v = line.split('=')
                variable_name = k.strip()
                variable_value = v.strip()

                parsed_value = self._parse_value(variable_value)
                group[variable_name] = parsed_value

            self.groups[group_name] = group

    def _parse_value(self, variable_value):
        """
        Tries to parse a single value, raises an exception if no single value is matched
        """
        try:
            parsed_value = int(variable_value)
        except ValueError:
            try:
                parsed_value = float(variable_value)
            except ValueError:
                if variable_value.lower() in ['.true.', 't']:
                    # boolean
                    parsed_value = True
                elif variable_value.lower() in ['.false.', 'f']:
                    parsed_value = False
                elif variable_value.startswith("'") \
                    and variable_value.endswith("'") \
                    and variable_value.count("'") == 2 \
                or variable_value.startswith('"') \
                    and variable_value.endswith('"') \
                    and variable_value.count('"') == 2:
                    # string
                    parsed_value = variable_value[1:-1]
                elif variable_value.startswith("/") and variable_value.endswith("/"):
                    # array /3,4,5/
                    parsed_value = []
                    for v in variable_value[1:-1].split(','):
                        parsed_value.append(self._parse_value(v))
                elif len(variable_value.split()) > 1:
                    # array 3 4 5
                    parsed_value = []
                    for v in variable_value.split(' '):
                        parsed_value.append(self._parse_value(v))
                else:
                    raise ValueError(variable_value)

        return parsed_value

    def dump(self, array_inline=True):
        lines = []
        for group_name, group_variables in self.groups.items():
            lines.append("&%s" % group_name)
            for variable_name, variable_value in group_variables.items():
                if isinstance(variable_value, list):
                    if array_inline:
                        lines.append("  %s = %s" % (variable_name, " ".join([self._format_value(v) for v in variable_value])))
                    else:
                        for n, v in enumerate(variable_value):
                            lines.append("  %s(%d) = %s" % (variable_name, n+1, self._format_value(v)))
                else:
                    lines.append("  %s = %s" % (variable_name, self._format_value(variable_value)))
            lines.append("/\n")

        return "\n".join(lines)

    def _format_value(self, value):
        if isinstance(value, bool):
            return value and '.true.' or '.false.'
        elif isinstance(value, int):
            return "%d" % value
        elif isinstance(value, float):
            # return "{:.3e}".format(value) # use exp. notation after 3 digits
            return "{}".format(value) # use exp. notation after 3 digits
        elif isinstance(value, str):
            return "'%s'" % value
        elif isinstance(value, complex):
            return "(%s,%s)" % (self._format_value(value.real), self._format_value(value.imag))
        else:
            raise Exception("Variable type not understood: %s" % type(value))

    @property
    def data(self):
        return AttributeMapper(self.groups)

#
# Here model-specific functions
#
def get_glacier_name():
    " get glacier name from control "
    control = read_namelist_file(NML_CONTROL)
    return control.groups['general']['name']

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
