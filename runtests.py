#!/usr/bin/env python
#
# Test runner for Travis
#
import os
import sys
import argparse
import unittest

import coverage


def get_args_parser():
    """Build the command line argument parser

    """
    parser = argparse.ArgumentParser(
        description='Load GAE and run the test modules '
            'found in the target directory.'
    )
    parser.add_argument(
        'start_dir',
        nargs='?',
        default='./webapp2ext/swagger/tests',
        help='directory to find test modules from (default to "./webapp2ext/swagger/tests").'
    )
    parser.add_argument(
        '--gae-lib-root', '-l',
        default=os.getenv('GAEPATH', '/usr/local/google_appengine'),
        help='directory where to find Google App Engine SDK '
            '(default to "/usr/local/google_appengine")'
    )
    parser.add_argument(
        '--with-cover', '-c',
        default=False, action='store_true',
        help='should run coverage.')
    parser.add_argument(
        '--cover-package', '-p',
        default='webapp2ext.swagger',
        help='list of package to mesure coverage for.'
    )
    return parser


def setup_gae(gae_lib_root):
    """Try to load Google App Engine SDK on Python 2.7.

    It shouldn't try to import to load it with Pyhton 2.6;
    dev_appserver exit on load with any other version than 2.7.

    setup_gae will fail quietly if it can't find the SDK.

    """
    if sys.version_info[0:2] != (2, 7,):
        return

    try:
        sys.path.insert(0, gae_lib_root)
        import dev_appserver
    except ImportError:
        print "Failed to load Google App Engine SDK."
        print "Google App Engine related tests will be skipped."
    else:
        dev_appserver.fix_sys_path()


def _run_test(suite):
    return unittest.TextTestRunner(verbosity=2, buffer=True).run(suite)

def _run_test_with_coverage(suite, source):
    cov = coverage.coverage(source=source)
    cov.start()

    results = unittest.TextTestRunner(verbosity=2, buffer=True).run(suite)
    cov.stop()
    cov.save()

    if results.wasSuccessful():
        print ""
        print "Coverage:"
        cov.report()
        cov.html_report()

    return results


def main(gae_lib_root, start_dir, with_coverage, source):
    """Try to load Google App Engine SDK and then to run any tests found with
    unittest discovery feature.

    If a test fail, it will exit with a status code of 1.

    """
    setup_gae(gae_lib_root)
    suite = unittest.loader.TestLoader().discover(start_dir)

    if with_coverage:
        results = _run_test_with_coverage(suite, source)
    else:
        results = _run_test(suite)

    if not results.wasSuccessful():
        sys.exit(1)


if __name__ == '__main__':
    parser = get_args_parser()
    args = parser.parse_args()
    main(
        args.gae_lib_root,
        args.start_dir,
        args.with_cover,
        args.cover_package.split(',')
    )
