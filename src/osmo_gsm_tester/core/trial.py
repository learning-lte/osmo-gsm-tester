# osmo_gsm_tester: trial: directory of binaries to be tested
#
# Copyright (C) 2016-2017 by sysmocom - s.f.m.c. GmbH
#
# Author: Neels Hofmeyr <neels@hofmeyr.de>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import time
import shutil
import tarfile
import pathlib

from . import log
from . import util
from . import report
from . import suite

FILE_MARK_TAKEN = 'taken'
FILE_CHECKSUMS = 'checksums.md5'
TIMESTAMP_FMT = '%Y-%m-%d_%H-%M-%S'
FILE_LAST_RUN = 'last_run'

class Trial(log.Origin):
    UNKNOWN = 'UNKNOWN'
    PASS = 'PASS'
    FAIL = 'FAIL'

    @staticmethod
    def next(trials_dir):

        with trials_dir.lock('Trial.next'):
            trials = [e for e in trials_dir.children()
                      if trials_dir.isdir(e) and not trials_dir.exists(e, FILE_MARK_TAKEN)]
            if not trials:
                return None
            # sort by time to get the one that waited longest
            trials.sort(key=lambda e: os.path.getmtime(trials_dir.child(e)))
            next_trial = trials[0]
            return Trial(trials_dir.child(next_trial)).take()

    def __init__(self, trial_dir):
        self.path = os.path.abspath(trial_dir)
        super().__init__(log.C_TST, os.path.basename(self.path))
        self.dir = util.Dir(self.path)
        self.inst_dir = util.Dir(self.dir.child('inst'))
        self.bin_tars = {}
        self.suites = []
        self.status = Trial.UNKNOWN
        self._run_dir = None
        self.log_targets = None

    def __repr__(self):
        return self.name()

    def __enter__(self):
        '''add a log target to log to the run dir, write taken marker, log a
        starting separator.'''
        run_dir = self.get_run_dir()
        detailed_log = run_dir.new_child(log.FILE_LOG)
        self.log_targets = [
            log.FileLogTarget(detailed_log)
              .set_all_levels(log.L_DBG)
              .style_change(trace=True),
            log.FileLogTarget(run_dir.new_child(log.FILE_LOG_BRIEF))
              .style_change(src=False, all_origins_on_levels=(log.L_ERR, log.L_TRACEBACK))
            ]
        log.large_separator(self.name(), sublevel=1)
        self.log('Detailed log at', detailed_log)
        self.take()
        return self

    def __exit__(self, *exc_info):
        '''log a report, then remove log file targets for this trial'''
        self.log_report()
        for lt in self.log_targets:
            lt.remove()
        self.log_targets = None

    def take(self):
        self.dir.touch(FILE_MARK_TAKEN)
        return self

    def get_run_dir(self):
        if self._run_dir is not None:
            return self._run_dir
        self._run_dir = util.Dir(self.dir.new_child('run.%s' % time.strftime(TIMESTAMP_FMT)))
        self._run_dir.mkdir()

        last_run = self.dir.child(FILE_LAST_RUN)
        if os.path.islink(last_run):
            os.remove(last_run)
        if not os.path.exists(last_run):
            os.symlink(self.dir.rel_path(self._run_dir.path), last_run)
        return self._run_dir

    def verify(self):
        "verify checksums"

        if not self.dir.exists():
            raise RuntimeError('Trial dir does not exist: %r' % self.dir)
        if not self.dir.isdir():
            raise RuntimeError('Trial dir is not a dir: %r' % self.dir)

        checksums = self.dir.child(FILE_CHECKSUMS)
        if not self.dir.isfile(FILE_CHECKSUMS):
            raise RuntimeError('No checksums file in trial dir: %r', checksums)

        with open(checksums, 'r') as f:
            line_nr = 0
            for line in [l.strip() for l in f.readlines()]:
                line_nr += 1
                if not line:
                    continue
                md5, relpath = line.split('  ')
                file_path = self.dir.child(relpath)

                if not self.dir.isfile(relpath):
                    raise RuntimeError('File listed in checksums file but missing in trials dir:'
                                       ' %r vs. %r line %d' % (file_path, checksums, line_nr))

                if md5 != util.md5_of_file(file_path):
                    raise RuntimeError('Checksum mismatch for %r vs. %r line %d'
                                       % (file_path, checksums, line_nr))

                if relpath.endswith('.tgz') or relpath.endswith('.tar.gz'):
                    (label, name) = os.path.split(relpath)
                    #print('label: %s, name: %s' % (label, name))
                    li = self.bin_tars.get(label, [])
                    li.append(name)
                    self.bin_tars[label] = li

    def has_bin_tar(self, bin_name, run_label):
        bin_tar_start = '%s.' % bin_name
        matches = [t for t in self.bin_tars[run_label] if t.startswith(bin_tar_start)]
        self.dbg('has bin_tar', run_label=run_label, bin_name=bin_name, matches=matches)
        if not matches:
            return None
        if len(matches) > 1:
            raise RuntimeError('More than one match for bin name %r on run_label \'%s\': %r' % (bin_name, run_label, matches))
        bin_tar = matches[0]
        bin_tar_path = self.dir.child(os.path.join(run_label, bin_tar))
        if not os.path.isfile(bin_tar_path):
            raise RuntimeError('Not a file or missing: %r' % bin_tar_path)
        return bin_tar_path

    def get_inst(self, bin_name, run_label=None):
        if run_label is None:
            run_label = ''
        bin_tar = self.has_bin_tar(bin_name, run_label)
        if not bin_tar:
            raise RuntimeError('No such binary available: %r' % bin_name)
        inst_dir = self.inst_dir.child(os.path.join(run_label, bin_name))

        if os.path.isdir(inst_dir):
            # already unpacked
            return inst_dir

        t = None
        try:
            os.makedirs(inst_dir)
            t = tarfile.open(bin_tar)
            t.extractall(inst_dir)
            return inst_dir

        except:
            shutil.rmtree(inst_dir)
            raise
        finally:
            if t:
                try:
                    t.close()
                except:
                    pass

    def add_suite_run(self, suite_scenario_str, suite_def, scenarios):
        suite_run = suite.SuiteRun(self, suite_scenario_str, suite_def, scenarios)
        self.suites.append(suite_run)

    def run_suites(self, names=None):
        self.status = Trial.UNKNOWN
        try:
            for suite_run in self.suites:
                try:
                    suite_run.run_tests(names)
                except BaseException as e:
                    # when the program is aborted by a signal (like Ctrl-C), escalate to abort all.
                    self.err('TRIAL RUN ABORTED: %s' % type(e).__name__)
                    # log the traceback before the trial's logging is ended
                    log.log_exn()
                    raise
                finally:
                    if suite_run.status != suite.SuiteRun.PASS:
                        self.status = Trial.FAIL
            if self.status == Trial.UNKNOWN:
                self.status = Trial.PASS
        finally:
            junit_path = self.get_run_dir().new_file(self.name()+'.xml')
            self.log('Storing JUnit report in', junit_path)
            report.trial_to_junit_write(self, junit_path)

    def get_all_inst_hash_info(self):
        d = {}
        pathlist = pathlib.Path(str(self.inst_dir)).glob('**/*git_hashes.txt')
        for path in pathlist:
            # because path is object not string
            abs_path_str = str(path) # because path is object not string
            dir, file = os.path.split(abs_path_str)
            reldir = os.path.relpath(dir, str(self.inst_dir)).rstrip(os.sep)
            with open(abs_path_str, 'r') as f:
                for line in [l.strip() for l in f.readlines()]:
                    if not line:
                        continue
                    hash, proj = tuple(line.split(' ', 1))
                d[os.path.join(reldir,proj)] = hash
        return d

    def log_report(self):
        log.large_separator(self.name(), self.status)
        self.log(report.trial_to_text(self))

# vim: expandtab tabstop=4 shiftwidth=4
