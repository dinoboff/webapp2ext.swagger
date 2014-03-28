"""Utility class and function for education test cases.

"""


import unittest

from google.appengine.datastore import datastore_stub_util
from google.appengine.ext import testbed


class TestCase(unittest.TestCase):
    """Basic Test case to extends

    Setup google appengine mock services.

    """

    def setUp(self):
        self.testbed = testbed.Testbed()
        # Then activate the testbed, which prepares the service stubs for use.
        self.testbed.activate()
        # Next, declare which service stubs you want to use.

        self.policy = datastore_stub_util.PseudoRandomHRConsistencyPolicy(
            probability=0
        )
        self.testbed.init_datastore_v3_stub(consistency_policy=self.policy)
        self.testbed.init_memcache_stub()
        self.testbed.init_taskqueue_stub(root_path="../.") #2.7
        self.testbed.init_user_stub()

    def tearDown(self):
        self.testbed.deactivate()

    def login(self, is_admin=False, user_id=1234):
        # Simulate User login
        self.testbed.setup_env(
            USER_EMAIL = 'test@example.com',
            USER_ID = str(user_id),
            USER_IS_ADMIN = '1' if is_admin else '0',
            overwrite = True)
