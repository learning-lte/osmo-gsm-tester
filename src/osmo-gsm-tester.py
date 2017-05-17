#!/usr/bin/env python3

# osmo_gsm_tester: invoke a single test run
#
# Copyright (C) 2016-2017 by sysmocom - s.f.m.c. GmbH
#
# Author: Neels Hofmeyr <neels@hofmeyr.de>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

'''osmo_gsm_tester: invoke a single test run.

Examples:

./run_once.py ~/my_trial_package/ -s osmo_trx
./run_once.py ~/my_trial_package/ -c sms_tests:dyn_ts+eu_band+bts_sysmo
./run_once.py ~/my_trial_package/ -c sms_tests/mo_mt_sms:bts_trx

(The names for test suite, scenario and series names used in these examples
must be defined by the osmo-gsm-tester configuration.)

A trial package contains binaries (usually built by a jenkins job) of GSM
software, including the core network programs as well as binaries for the
various BTS models.

A test suite defines specific actions to be taken and verifies their outcome.
Such a test suite may leave certain aspects of a setup undefined, e.g. it may
be BTS model agnostic or does not care which voice codecs are chosen.

A test scenario completes the picture in that it defines which specific choices
shall be made to run a test suite. Any one test suite may thus run on any
number of different scenarios, e.g. to test various voice codecs.

Test scenarios may be combined. For example, one scenario may define a timeslot
configuration to use, while another scenario may define the voice codec
configuration.

There may still be aspects that are neither required by a test suite nor
strictly defined by a scenario, which will be resolved automatically, e.g. by
choosing the first available item that matches the other constraints.

A test run thus needs to define: a trial package containing built binaries, a
combination of scenarios to run a suite in, and a test suite to launch in the
given scenario with the given binaries.

The osmo-gsm-tester configuration may define one or more series as a number of
suite:scenario combinations. So instead of a specific suite:scenario
combination, the name of such a series can be passed.

If neither a combination or series is specified, the default series will be run
as defined in the osmo-gsm-tester configuration.

The scenarios and suites run for a given trial will be recorded in a trial
package's directory: Upon launch, a 'test_package/run.<date>' directory will be
created, which will collect logs and reports.
'''

import sys
import argparse
from signal import *
from osmo_gsm_tester import __version__
from osmo_gsm_tester import trial, suite, log, config

def sig_handler_cleanup(signum, frame):
    print("killed by signal %d" % signum)
    # This sys.exit() will raise a SystemExit base exception at the current
    # point of execution. Code must be prepared to clean system-wide resources
    # by using the "finally" section. This allows at the end 'atexit' hooks to
    # be called before exiting.
    sys.exit(1)

def main():

    for sig in (SIGINT, SIGTERM, SIGQUIT, SIGPIPE, SIGHUP):
        signal(sig, sig_handler_cleanup)

    parser = argparse.ArgumentParser(epilog=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    # Note: since we're using RawTextHelpFormatter to keep nicely separate
    # paragraphs in the long help text, we unfortunately also need to take care
    # of line wraps in the shorter cmdline options help.
    # The line width here is what remains of screen width after the list of
    # options placed by ArgumentParser. That's unfortunately subject to change
    # and undefined, so when things change, just run a local
    # ./osmo-gsm-tester.py --help and try to keep everything in 80 chars width.
    # The help text is indented automatically, but line width is manual.
    # Using multi-line strings here -- doesn't look nice in the python flow but
    # is easiest to maintain.
    parser.add_argument('-V', '--version', action='store_true',
            help='Show version')
    parser.add_argument('trial_package', nargs='+',
            help='Directory containing binaries to test')
    parser.add_argument('-s', '--suite-scenario', dest='suite_scenario', action='append',
            help='''A suite-scenarios combination
like suite:scenario+scenario''')
    parser.add_argument('-S', '--series', dest='series', action='append',
            help='''A series of suite-scenarios combinations
as defined in the osmo-gsm-tester configuration''')
    parser.add_argument('-t', '--test', dest='test', action='append',
            help='''Run only tests matching this name.
Any test name that contains the given string is run.
To get an exact match, prepend a "=" like
"-t =my_exact_name". The ".py" suffix is always
optional.''')
    parser.add_argument('-l', '--log-level', dest='log_level', choices=log.LEVEL_STRS.keys(),
            default=None,
            help='Set logging level for all categories (on stdout)')
    parser.add_argument('-T', '--traceback', dest='trace', action='store_true',
            help='Enable logging of tracebacks')
    args = parser.parse_args()

    if args.version:
        print(__version__)
        exit(0)

    print('combinations:', repr(args.suite_scenario))
    print('series:', repr(args.series))
    print('trials:', repr(args.trial_package))
    print('tests:', repr(args.test))

    # create a default log to stdout
    log.LogTarget().style(all_origins=False, src=False)

    if args.log_level:
        log.set_all_levels(log.LEVEL_STRS.get(args.log_level))
    if args.trace:
        log.style_change(trace=True)

    combination_strs = list(args.suite_scenario or [])
    # for series in args.series:
    #     combination_strs.extend(config.get_series(series))

    if not combination_strs:
        combination_strs = config.read_config_file(config.DEFAULT_SUITES_CONF, if_missing_return=[])

        if combination_strs:
            print('Running default suites:\n  ' + ('\n  '.join(combination_strs)))
        else:
            print('No default suites configured (%r)' % config.DEFAULT_SUITES_CONF)


    if not combination_strs:
        raise RuntimeError('Need at least one suite:scenario or series to run')

    suite_scenarios = []
    for combination_str in combination_strs:
        suite_scenarios.append(suite.load_suite_scenario_str(combination_str))

    test_names = []
    for test_name in (args.test or []):
        found = False
        if test_name.startswith('=') and not test_name.endswith('.py'):
            test_name = test_name + '.py'
        for suite_scenario_str, suite_def, scenarios in suite_scenarios:
            for test in suite_def.tests:
                if test_name.startswith('='):
                    match = test_name[1:] == test.name()
                else:
                    match = test_name in test.name()
                if match:
                    found = True
                    test_names.append(test.name())
        if not found:
            raise RuntimeError('No test found for %r' % test_name)
    if test_names:
        print(repr(test_names))

    trials = []
    for trial_package in args.trial_package:
        t = trial.Trial(trial_package)
        t.verify()
        trials.append(t)

    trials_run = []
    any_failed = False

    for current_trial in trials:
        try:
            with current_trial:
                for suite_scenario_str, suite_def, scenarios in suite_scenarios:
                    log.large_separator(current_trial.name(), suite_scenario_str)
                    suite_run = suite.SuiteRun(current_trial, suite_scenario_str, suite_def, scenarios)
                    current_trial.add_suite(suite_run)

                status = current_trial.run_suites(test_names)
                if status == trial.Trial.FAIL:
                    any_failed = True
                trials_run.append(current_trial)
        except Exception:
            # Do not catch here subclasses of BaseException such as SystemExit, let them finish the program
            current_trial.log_exn()

    sys.stderr.flush()
    sys.stdout.flush()
    if not any_failed:
            log.large_separator('All trials passed:\n  ' + ('\n  '.join(mytrial.name() for mytrial in trials_run)))
    else:
        for mytrial in trials_run:
            log.large_separator('Trial Report for %s' % mytrial.name())
            mytrial.log_report()
        exit(1)

if __name__ == '__main__':
    try:
        main()
    except:
        # Tell the log to show the exception, then terminate the program with the exception anyway.
        # Since exceptions within test runs should be caught and evaluated, this is basically about
        # exceptions during command line parsing and such, so it's appropriate to abort immediately.
        log.log_exn()
        raise

# vim: expandtab tabstop=4 shiftwidth=4
