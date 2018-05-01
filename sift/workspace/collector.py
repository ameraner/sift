#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PURPOSE
Collector is a zookeeper of products, which populates and revises the workspace metadatabase
 Collector uses Hunters to find individual formats/conventions/products
 Products live in Resources (typically files)
 Collector skims files without reading data
 Collector populates the metadatabase with information about available products
 More than one Product may be in a Resource

 Collector also knows which Importer can bring Content from the Resource into the Workspace

REFERENCES

REQUIRES

:author: R.K.Garcia <rkgarcia@wisc.edu>
:copyright: 2017 by University of Wisconsin Regents, see AUTHORS for more details
:license: GPLv3, see LICENSE for more details
"""
import os, sys
import logging, unittest
from PyQt4.QtCore import QObject, pyqtSignal
from typing import Union, Set, List, Iterable, Mapping
from ..common import INFO
from .workspace import Workspace
from sift.queue import TASK_DOING, TASK_PROGRESS
from datetime import datetime


LOG = logging.getLogger(__name__)


class _workspace_test_proxy(object):
    def __init__(self):
        self.cwd = '/tmp' if os.path.isdir("/tmp") else os.getcwd()

    def collect_product_metadata_for_paths(self, paths):
        LOG.debug("import metadata for files: {}".format(repr(paths)))
        for path in paths:
            yield {INFO.PATHNAME: path}


class ResourceSearchPathCollector(QObject):
    """Given a set of search paths,
    awaken for new files available within the directories,
    update the metadatabase for new resources,
    and mark for purge any files no longer available.
    """
    _ws: Workspace = None
    _paths: List[str] = None
    _dir_mtimes: Mapping[str, datetime] = None
    _timestamp_path: str = None  # path which tracks the last time we skimmed the paths
    _is_posix: bool = None
    _scheduled_files: List[str] = None

    @property
    def paths(self):
        return list(self._paths)

    @paths.setter
    def paths(self, new_paths):
        nu = set(new_paths)
        ol = set(self._paths)
        removed = ol - nu
        added = nu - ol
        self._paths = list(new_paths)
        self._flush_dirs(removed)
        self._schedule_walk_dirs(added)

    def _flush_dirs(self, dirs: Iterable[str]):
        pass

    def _schedule_walk_dirs(self, dirs: Iterable[str]):
        pass

    @property
    def has_pending_files(self):
        return len(self._scheduled_files) > 0

    def _skim(self, last_checked: int = None):
        """skim directories for new mtimes
        """
        for rawpath in self._paths:
            path = os.path.realpath(rawpath)
            if not os.path.isdir(path):
                LOG.warning("{} is not a directory".format(path))
                continue
            for dirpath, dirnames, filenames in os.walk(path):
                if self._is_posix and (os.stat(dirpath).st_mtime < last_checked):
                    LOG.debug("skipping files in {} due to POSIX directory mtime".format(dirpath))
                    continue
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    if os.path.isfile(filepath) and (os.stat(filepath).st_mtime >= last_checked):
                        yield filepath

    def _touch(self):
        mtime = 0
        if os.path.isfile(self._timestamp_path):
            mtime = os.stat(self._timestamp_path).st_mtime
        else:
            with open(self._timestamp_path, 'wb') as fp:
                fp.close()
        os.utime(self._timestamp_path)
        return mtime

    def __init__(self, ws: [Workspace, _workspace_test_proxy]):
        super(ResourceSearchPathCollector, self).__init__()
        self._ws = ws
        self._paths = []
        self._dir_mtimes = {}
        self._scheduled_files = []
        self._timestamp_path = os.path.join(ws.cwd, '.last_collection_check')
        self._is_posix = sys.platform in {'linux', 'darwin'}

    def look_for_new_files(self):
        when = self._touch()
        new_files = list(self._skim(when))
        if new_files:
            LOG.info('found {} new files to skim metadata for'.format(len(new_files)))
            self._scheduled_files += new_files

    def bgnd_look_for_new_files(self):
        yield {TASK_DOING: 'skimming', TASK_PROGRESS: 0.5}
        self.look_for_new_files()
        yield {TASK_DOING: 'skimming', TASK_PROGRESS: 1.0}

    def bgnd_merge_new_file_metadata_into_mdb(self):
        todo, self._scheduled_files = self._scheduled_files, []
        ntodo = len(todo)
        redex = dict((name, dex) for (dex, name) in enumerate(todo))
        yield {TASK_DOING: 'merging metadata 0/{}'.format(ntodo), TASK_PROGRESS: 0.0}
        for product_info in self._ws.collect_product_metadata_for_paths(todo):
            path = product_info.get(INFO.PATHNAME, None)
            dex = redex.get(path, 0.0)
            yield {TASK_DOING: 'merging metadata {}/{}'.format(dex+1, ntodo), TASK_PROGRESS: float(dex)/float(ntodo)}
        yield {TASK_DOING: 'merging metadata done', TASK_PROGRESS: 1.0}


def _debug(type, value, tb):
    "enable with sys.excepthook = debug"
    if not sys.stdin.isatty():
        sys.__excepthook__(type, value, tb)
    else:
        import traceback, pdb
        traceback.print_exception(type, value, tb)
        # …then start the debugger in post-mortem mode.
        pdb.post_mortem(tb)  # more “modern”


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="PURPOSE",
        epilog="",
        fromfile_prefix_chars='@')
    parser.add_argument('-v', '--verbose', dest='verbosity', action="count", default=0,
                        help='each occurrence increases verbosity 1 level through ERROR-WARNING-INFO-DEBUG')
    parser.add_argument('-d', '--debug', dest='debug', action='store_true',
                        help="enable interactive PDB debugger on exception")
    parser.add_argument('inputs', nargs='*',
                        help="input files to process")
    args = parser.parse_args()

    levels = [logging.ERROR, logging.WARN, logging.INFO, logging.DEBUG]
    logging.basicConfig(level=levels[min(3, args.verbosity)])

    if args.debug:
        sys.excepthook = _debug

    if not args.inputs:
        unittest.main()
        return 0

    ws = _workspace_test_proxy()
    collector = ResourceSearchPathCollector(ws)
    collector.paths = list(args.inputs)

    collector.look_for_new_files()
    if collector.has_pending_files:
        for progress in collector.bgnd_merge_new_file_metadata_into_mdb():
            LOG.debug(repr(progress))

    return 0


if __name__ == '__main__':
    sys.exit(main())
