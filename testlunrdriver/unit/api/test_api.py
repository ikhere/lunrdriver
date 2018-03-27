import mock

from cinder import context
from cinder import db
from cinder import exception
from cinder import test
from cinder.volume import volume_types
from cinder.tests.unit import utils as tests_utils

from lunrdriver.lunr import api as lunr_api
from lunrdriver.lunr.client import LunrTypeResource


def_vol_type = 'vtype'


def _get_volume_type(*args, **kwargs):
    class MockResponse(object):
        pass
    resp = MockResponse()
    resp.body = {'min_size': 2, 'max_size': 10}
    return resp


class TestLunrAPI(test.TestCase):

    def setUp(self):
        super(TestLunrAPI, self).setUp()
        self.context = context.get_admin_context()
        self.flags(default_volume_type=def_vol_type)
        volume_types.create(self.context, def_vol_type)
        self.flags(lunr_volume_types=[def_vol_type, ])

    @mock.patch.object(LunrTypeResource, 'get', _get_volume_type)
    def test_create_volume(self):
        api = lunr_api.API()
        volume_type = volume_types.get_default_volume_type()
        volume = api.create(self.context, 10, 'fake-volume', 'fake volume')
        self.assertEqual(volume['volume_type_id'], volume_type['id'])

    @mock.patch.object(LunrTypeResource, 'get', _get_volume_type)
    def test_create_invalid_size_volume(self):
        api = lunr_api.API()
        self.assertRaises(
            exception.InvalidInput, api.create,
            self.context, 1, 'fake-volume', 'fake volume')

    def test_create_snapshot(self):
        volume_type = volume_types.get_default_volume_type()
        volume = tests_utils.create_volume(
            self.context, volume_type_id=volume_type['id'])
        api = lunr_api.API()
        snapshot = api.create_snapshot(
            self.context, volume, 'fake-snapshot', 'fake snapshot')
        self.assertEqual(snapshot['status'], 'creating')

    def test_create_snapshot_conflict(self):
        volume_type = volume_types.get_default_volume_type()
        volume = tests_utils.create_volume(
            self.context, volume_type_id=volume_type['id'])
        # create a snapshot record
        tests_utils.create_snapshot(self.context, volume['id'],
                                    status='creating')
        api = lunr_api.API()
        self.assertRaises(
            exception.Invalid, api.create_snapshot,
            self.context, volume, 'fake-snapshot', 'fake snapshot')

    def test_create_snapshot_conflict_with_force(self):
        volume_type = volume_types.get_default_volume_type()
        volume = tests_utils.create_volume(
            self.context, volume_type_id=volume_type['id'])
        # create a snapshot record
        tests_utils.create_snapshot(self.context, volume['id'],
                                    status='creating')
        api = lunr_api.API()
        snapshot = api.create_snapshot_force(
            self.context, volume, 'force-snapshot', 'force snapshot')
        self.assertEqual(snapshot['status'], 'creating')

    def test_delete_volume_in_error_deleting_status(self):
        volume_type = volume_types.get_default_volume_type()
        volume = tests_utils.create_volume(
            self.context, status='error_deleting',
            volume_type_id=volume_type['id'])
        api = lunr_api.API()
        api.delete(self.context, volume)
        post_delete = db.volume_get(self.context, volume['id'])
        self.assertIsNot(volume['status'], post_delete['status'])
        self.assertEqual(post_delete['status'], 'deleting')

    def test_delete_snapshot_in_error_deleting_status(self):
        volume_type = volume_types.get_default_volume_type()
        volume = tests_utils.create_volume(
            self.context, volume_type_id=volume_type['id'])
        snapshot = tests_utils.create_snapshot(
            self.context, volume['id'], status='error_deleting')
        # explicitly set volume_type_id in stub
        snapshot['volume_type_id'] = volume_type['id']
        api = lunr_api.API()
        api.delete_snapshot(self.context, snapshot)
        post_delete = db.snapshot_get(self.context, snapshot['id'])
        self.assertIsNot(snapshot['status'], post_delete['status'])
        self.assertEqual(post_delete['status'], 'deleting')

    def test_delete_snapshot_conflict(self):
        volume_type = volume_types.get_default_volume_type()
        volume = tests_utils.create_volume(
            self.context, volume_type_id=volume_type['id'])
        # create conflicting snapshot
        tests_utils.create_snapshot(self.context, volume['id'])
        snapshot = tests_utils.create_snapshot(
            self.context, volume['id'], status='available')
        # explicitly set volume_type_id in stub
        snapshot['volume_type_id'] = volume_type['id']
        api = lunr_api.API()
        self.assertRaises(
            exception.Invalid, api.delete_snapshot,
            self.context, snapshot)

    def test_delete_snapshot_conflict_with_force(self):
        volume_type = volume_types.get_default_volume_type()
        volume = tests_utils.create_volume(
            self.context, volume_type_id=volume_type['id'])
        # create conflicting snapshot
        tests_utils.create_snapshot(self.context, volume['id'])
        snapshot = tests_utils.create_snapshot(
            self.context, volume['id'], status='available')
        # explicitly set volume_type_id in stub
        snapshot['volume_type_id'] = volume_type['id']
        api = lunr_api.API()
        api.delete_snapshot(self.context, snapshot, force=True)
        post_delete = db.snapshot_get(self.context, snapshot['id'])
        self.assertIsNot(snapshot['status'], post_delete['status'])
        self.assertEqual(post_delete['status'], 'deleting')
