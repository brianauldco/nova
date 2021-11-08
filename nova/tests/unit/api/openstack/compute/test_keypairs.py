# Copyright 2011 Eldar Nugaev
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import mock
import webob

from nova.api.openstack.compute import keypairs as keypairs_v21
from nova.api.openstack import wsgi as os_wsgi
from nova import context as nova_context
from nova import exception
from nova import objects
from nova import quota
from nova import test
from nova.tests.unit.api.openstack import fakes
from nova.tests.unit.objects import test_keypair


QUOTAS = quota.QUOTAS


keypair_data = {
    'public_key': 'FAKE_KEY',
    'fingerprint': 'FAKE_FINGERPRINT',
}

FAKE_UUID = 'b48316c5-71e8-45e4-9884-6c78055b9b13'


def fake_keypair(name):
    return dict(test_keypair.fake_keypair,
                name=name, **keypair_data)


def _fake_get_from_db(context, user_id, name=None, limit=None, marker=None):
    if name:
        if name != 'FAKE':
            raise exception.KeypairNotFound(user_id=user_id, name=name)
        return fake_keypair('FAKE')
    return [fake_keypair('FAKE')]


def _fake_get_count_from_db(context, user_id):
    return 1


def _fake_create_in_db(context, values):
    return fake_keypair(name=values['name'])


def _fake_destroy_in_db(context, user_id, name):
    if not (user_id and name):
        raise Exception()

    if name != 'FAKE':
        raise exception.KeypairNotFound(user_id=user_id, name=name)


def db_key_pair_create_duplicate(context):
    raise exception.KeyPairExists(key_name='create_duplicate')


class KeypairsTestV21(test.TestCase):
    base_url = '/v2/%s' % fakes.FAKE_PROJECT_ID
    validation_error = exception.ValidationError
    wsgi_api_version = os_wsgi.DEFAULT_API_VERSION

    def _setup_app_and_controller(self):
        self.app_server = fakes.wsgi_app_v21()
        self.controller = keypairs_v21.KeypairController()

    def setUp(self):
        super(KeypairsTestV21, self).setUp()
        fakes.stub_out_networking(self)
        fakes.stub_out_secgroup_api(self)

        self.stub_out(
            'nova.objects.keypair._create_in_db', _fake_create_in_db)
        self.stub_out(
            'nova.objects.keypair._destroy_in_db', _fake_destroy_in_db)
        self.stub_out(
            'nova.objects.keypair._get_from_db', _fake_get_from_db)
        self.stub_out(
            'nova.objects.keypair._get_count_from_db', _fake_get_count_from_db)

        self._setup_app_and_controller()

        self.req = fakes.HTTPRequest.blank('', version=self.wsgi_api_version)

    def test_keypair_list(self):
        res_dict = self.controller.index(self.req)
        response = {'keypairs': [{'keypair': dict(keypair_data, name='FAKE')}]}
        self.assertEqual(res_dict, response)

    def test_keypair_create(self):
        body = {'keypair': {'name': 'create_test'}}
        res_dict = self.controller.create(self.req, body=body)
        self.assertGreater(len(res_dict['keypair']['fingerprint']), 0)
        self.assertGreater(len(res_dict['keypair']['private_key']), 0)
        self._assert_keypair_type(res_dict)

    def _test_keypair_create_bad_request_case(self,
                                              body,
                                              exception):
        self.assertRaises(exception,
                          self.controller.create, self.req, body=body)

    def test_keypair_create_with_empty_name(self):
        body = {'keypair': {'name': ''}}
        self._test_keypair_create_bad_request_case(body,
                                                   self.validation_error)

    def test_keypair_create_with_name_too_long(self):
        body = {
            'keypair': {
                'name': 'a' * 256
            }
        }
        self._test_keypair_create_bad_request_case(body,
                                                   self.validation_error)

    def test_keypair_create_with_name_leading_trailing_spaces(self):
        body = {
            'keypair': {
                'name': '  test  '
            }
        }
        self._test_keypair_create_bad_request_case(body,
                                                   self.validation_error)

    def test_keypair_create_with_name_leading_trailing_spaces_compat_mode(
            self):
        body = {'keypair': {'name': '  test  '}}
        self.req.set_legacy_v2()
        res_dict = self.controller.create(self.req, body=body)
        self.assertEqual('test', res_dict['keypair']['name'])

    def test_keypair_create_with_non_alphanumeric_name(self):
        body = {
            'keypair': {
                'name': 'test/keypair'
            }
        }
        self._test_keypair_create_bad_request_case(body,
                                                   webob.exc.HTTPBadRequest)

    def test_keypair_import_bad_key(self):
        body = {
            'keypair': {
                'name': 'create_test',
                'public_key': 'ssh-what negative',
            },
        }
        self._test_keypair_create_bad_request_case(body,
                                                   webob.exc.HTTPBadRequest)

    def test_keypair_create_with_invalid_keypair_body(self):
        body = {'alpha': {'name': 'create_test'}}
        self._test_keypair_create_bad_request_case(body,
                                                   self.validation_error)

    def test_keypair_import(self):
        body = {
            'keypair': {
                'name': 'create_test',
                'public_key': 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDBYIznA'
                              'x9D7118Q1VKGpXy2HDiKyUTM8XcUuhQpo0srqb9rboUp4'
                              'a9NmCwpWpeElDLuva707GOUnfaBAvHBwsRXyxHJjRaI6Y'
                              'Qj2oLJwqvaSaWUbyT1vtryRqy6J3TecN0WINY71f4uymi'
                              'MZP0wby4bKBcYnac8KiCIlvkEl0ETjkOGUq8OyWRmn7lj'
                              'j5SESEUdBP0JnuTFKddWTU/wD6wydeJaUhBTqOlHn0kX1'
                              'GyqoNTE1UEhcM5ZRWgfUZfTjVyDF2kGj3vJLCJtJ8LoGc'
                              'j7YaN4uPg1rBle+izwE/tLonRrds+cev8p6krSSrxWOwB'
                              'bHkXa6OciiJDvkRzJXzf',
            },
        }
        res_dict = self.controller.create(self.req, body=body)
        # FIXME(ja): Should we check that public_key was sent to create?
        self.assertGreater(len(res_dict['keypair']['fingerprint']), 0)
        self.assertNotIn('private_key', res_dict['keypair'])
        self._assert_keypair_type(res_dict)

    @mock.patch('nova.objects.Quotas.check_deltas')
    def test_keypair_import_quota_limit(self, mock_check):
        mock_check.side_effect = exception.OverQuota(overs='key_pairs',
                                                     usages={'key_pairs': 100})
        body = {
            'keypair': {
                'name': 'create_test',
                'public_key': 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDBYIznA'
                              'x9D7118Q1VKGpXy2HDiKyUTM8XcUuhQpo0srqb9rboUp4'
                              'a9NmCwpWpeElDLuva707GOUnfaBAvHBwsRXyxHJjRaI6Y'
                              'Qj2oLJwqvaSaWUbyT1vtryRqy6J3TecN0WINY71f4uymi'
                              'MZP0wby4bKBcYnac8KiCIlvkEl0ETjkOGUq8OyWRmn7lj'
                              'j5SESEUdBP0JnuTFKddWTU/wD6wydeJaUhBTqOlHn0kX1'
                              'GyqoNTE1UEhcM5ZRWgfUZfTjVyDF2kGj3vJLCJtJ8LoGc'
                              'j7YaN4uPg1rBle+izwE/tLonRrds+cev8p6krSSrxWOwB'
                              'bHkXa6OciiJDvkRzJXzf',
            },
        }

        ex = self.assertRaises(webob.exc.HTTPForbidden,
                               self.controller.create, self.req, body=body)
        self.assertIn('Quota exceeded, too many key pairs.', ex.explanation)

    @mock.patch('nova.objects.Quotas.check_deltas')
    def test_keypair_create_quota_limit(self, mock_check):
        mock_check.side_effect = exception.OverQuota(overs='key_pairs',
                                                     usages={'key_pairs': 100})
        body = {
            'keypair': {
                'name': 'create_test',
            },
        }

        ex = self.assertRaises(webob.exc.HTTPForbidden,
                               self.controller.create, self.req, body=body)
        self.assertIn('Quota exceeded, too many key pairs.', ex.explanation)

    @mock.patch('nova.objects.Quotas.check_deltas')
    def test_keypair_create_over_quota_during_recheck(self, mock_check):
        # Simulate a race where the first check passes and the recheck fails.
        # First check occurs in compute/api.
        exc = exception.OverQuota(overs='key_pairs', usages={'key_pairs': 100})
        mock_check.side_effect = [None, exc]
        body = {
            'keypair': {
                'name': 'FAKE',
            },
        }

        self.assertRaises(webob.exc.HTTPForbidden,
                          self.controller.create, self.req, body=body)

        ctxt = self.req.environ['nova.context']
        self.assertEqual(2, mock_check.call_count)
        call1 = mock.call(ctxt, {'key_pairs': 1}, ctxt.user_id)
        call2 = mock.call(ctxt, {'key_pairs': 0}, ctxt.user_id)
        mock_check.assert_has_calls([call1, call2])

        # Verify we removed the key pair that was added after the first
        # quota check passed.
        key_pairs = objects.KeyPairList.get_by_user(ctxt, ctxt.user_id)
        names = [key_pair.name for key_pair in key_pairs]
        self.assertNotIn('create_test', names)

    @mock.patch('nova.objects.Quotas.check_deltas')
    def test_keypair_create_no_quota_recheck(self, mock_check):
        # Disable recheck_quota.
        self.flags(recheck_quota=False, group='quota')

        body = {
            'keypair': {
                'name': 'create_test',
            },
        }
        self.controller.create(self.req, body=body)

        ctxt = self.req.environ['nova.context']
        # check_deltas should have been called only once.
        mock_check.assert_called_once_with(ctxt, {'key_pairs': 1},
                                           ctxt.user_id)

    def test_keypair_create_duplicate(self):
        self.stub_out("nova.objects.KeyPair.create",
                      db_key_pair_create_duplicate)
        body = {'keypair': {'name': 'create_duplicate'}}
        ex = self.assertRaises(webob.exc.HTTPConflict,
                               self.controller.create, self.req, body=body)
        self.assertIn("Key pair 'create_duplicate' already exists.",
                      ex.explanation)

    @mock.patch('nova.objects.KeyPair.get_by_name')
    def test_keypair_delete(self, mock_get_by_name):
        mock_get_by_name.return_value = objects.KeyPair(
            nova_context.get_admin_context(), **fake_keypair('FAKE'))
        self.controller.delete(self.req, 'FAKE')

    def test_keypair_get_keypair_not_found(self):
        self.assertRaises(webob.exc.HTTPNotFound,
                          self.controller.show, self.req, 'DOESNOTEXIST')

    def test_keypair_delete_not_found(self):
        self.assertRaises(webob.exc.HTTPNotFound,
                          self.controller.delete, self.req, 'DOESNOTEXIST')

    def test_keypair_show(self):
        res_dict = self.controller.show(self.req, 'FAKE')
        self.assertEqual('FAKE', res_dict['keypair']['name'])
        self.assertEqual('FAKE_KEY', res_dict['keypair']['public_key'])
        self.assertEqual(
            'FAKE_FINGERPRINT', res_dict['keypair']['fingerprint'])
        self._assert_keypair_type(res_dict)

    def test_keypair_show_not_found(self):
        self.assertRaises(webob.exc.HTTPNotFound,
                          self.controller.show, self.req, 'DOESNOTEXIST')

    def _assert_keypair_type(self, res_dict):
        self.assertNotIn('type', res_dict['keypair'])


class KeypairsTestV22(KeypairsTestV21):
    wsgi_api_version = '2.2'

    def test_keypair_list(self):
        res_dict = self.controller.index(self.req)
        expected = {'keypairs': [{'keypair': dict(keypair_data, name='FAKE',
                                                  type='ssh')}]}
        self.assertEqual(expected, res_dict)

    def _assert_keypair_type(self, res_dict):
        self.assertEqual('ssh', res_dict['keypair']['type'])

    def test_keypair_create_with_name_leading_trailing_spaces_compat_mode(
            self):
        pass

    def test_create_server_keypair_name_with_leading_trailing_compat_mode(
            self):
        pass


class KeypairsTestV210(KeypairsTestV22):
    wsgi_api_version = '2.10'

    def test_keypair_create_with_name_leading_trailing_spaces_compat_mode(
            self):
        pass

    def test_create_server_keypair_name_with_leading_trailing_compat_mode(
            self):
        pass

    def test_keypair_list_other_user(self):
        req = fakes.HTTPRequest.blank(self.base_url +
                                      '/os-keypairs?user_id=foo',
                                      version=self.wsgi_api_version,
                                      use_admin_context=True)
        with mock.patch.object(self.controller.api, 'get_key_pairs') as mock_g:
            self.controller.index(req)
            userid = mock_g.call_args_list[0][0][1]
            self.assertEqual('foo', userid)

    def test_keypair_show_other_user(self):
        req = fakes.HTTPRequest.blank(self.base_url +
                                      '/os-keypairs/FAKE?user_id=foo',
                                      version=self.wsgi_api_version,
                                      use_admin_context=True)
        with mock.patch.object(self.controller.api, 'get_key_pair') as mock_g:
            self.controller.show(req, 'FAKE')
            userid = mock_g.call_args_list[0][0][1]
            self.assertEqual('foo', userid)

    def test_keypair_delete_other_user(self):
        req = fakes.HTTPRequest.blank(self.base_url +
                                      '/os-keypairs/FAKE?user_id=foo',
                                      version=self.wsgi_api_version,
                                      use_admin_context=True)
        with mock.patch.object(self.controller.api,
                               'delete_key_pair') as mock_g:
            self.controller.delete(req, 'FAKE')
            userid = mock_g.call_args_list[0][0][1]
            self.assertEqual('foo', userid)

    def test_keypair_create_other_user(self):
        req = fakes.HTTPRequest.blank(self.base_url +
                                      '/os-keypairs',
                                      version=self.wsgi_api_version,
                                      use_admin_context=True)
        body = {'keypair': {'name': 'create_test',
                            'user_id': '8861f37f-034e-4ca8-8abe-6d13c074574a'}}
        with mock.patch.object(self.controller.api,
                               'create_key_pair',
                               return_value=(mock.MagicMock(), 1)) as mock_g:
            res = self.controller.create(req, body=body)
            userid = mock_g.call_args_list[0][0][1]
            self.assertEqual('8861f37f-034e-4ca8-8abe-6d13c074574a', userid)
        self.assertIn('keypair', res)

    def test_keypair_import_other_user(self):
        req = fakes.HTTPRequest.blank(self.base_url +
                                      '/os-keypairs',
                                      version=self.wsgi_api_version,
                                      use_admin_context=True)
        body = {'keypair': {'name': 'create_test',
                            'user_id': '8861f37f-034e-4ca8-8abe-6d13c074574a',
                            'public_key': 'public_key'}}
        with mock.patch.object(self.controller.api,
                               'import_key_pair') as mock_g:
            res = self.controller.create(req, body=body)
            userid = mock_g.call_args_list[0][0][1]
            self.assertEqual('8861f37f-034e-4ca8-8abe-6d13c074574a', userid)
        self.assertIn('keypair', res)

    def test_keypair_list_other_user_invalid_in_old_microversion(self):
        req = fakes.HTTPRequest.blank(self.base_url +
                                      '/os-keypairs?user_id=foo',
                                      version="2.9",
                                      use_admin_context=True)
        with mock.patch.object(self.controller.api, 'get_key_pairs') as mock_g:
            self.controller.index(req)
            userid = mock_g.call_args_list[0][0][1]
            self.assertEqual('fake_user', userid)


class KeypairsTestV235(test.TestCase):
    base_url = '/v2/%s' % fakes.FAKE_PROJECT_ID
    wsgi_api_version = '2.35'

    def _setup_app_and_controller(self):
        self.app_server = fakes.wsgi_app_v21()
        self.controller = keypairs_v21.KeypairController()

    def setUp(self):
        super(KeypairsTestV235, self).setUp()
        self._setup_app_and_controller()

    @mock.patch('nova.objects.keypair._get_from_db')
    def test_keypair_list_limit_and_marker(self, mock_kp_get):
        mock_kp_get.side_effect = _fake_get_from_db

        req = fakes.HTTPRequest.blank(
            self.base_url + '/os-keypairs?limit=3&marker=fake_marker',
            version=self.wsgi_api_version, use_admin_context=True)

        res_dict = self.controller.index(req)

        mock_kp_get.assert_called_once_with(
            req.environ['nova.context'], 'fake_user',
            limit=3, marker='fake_marker')
        response = {'keypairs': [{'keypair': dict(keypair_data, name='FAKE',
                                                  type='ssh')}]}
        self.assertEqual(res_dict, response)

    @mock.patch('nova.compute.api.KeypairAPI.get_key_pairs')
    def test_keypair_list_limit_and_marker_invalid_marker(self, mock_kp_get):
        mock_kp_get.side_effect = exception.MarkerNotFound(marker='unknown_kp')

        req = fakes.HTTPRequest.blank(
            self.base_url + '/os-keypairs?limit=3&marker=unknown_kp',
            version=self.wsgi_api_version, use_admin_context=True)

        self.assertRaises(webob.exc.HTTPBadRequest, self.controller.index, req)

    def test_keypair_list_limit_and_marker_invalid_limit(self):
        req = fakes.HTTPRequest.blank(
            self.base_url + '/os-keypairs?limit=abc&marker=fake_marker',
            version=self.wsgi_api_version, use_admin_context=True)

        self.assertRaises(exception.ValidationError, self.controller.index,
                          req)

    @mock.patch('nova.objects.keypair._get_from_db')
    def test_keypair_list_limit_and_marker_invalid_in_old_microversion(
        self, mock_kp_get,
    ):
        mock_kp_get.side_effect = _fake_get_from_db

        req = fakes.HTTPRequest.blank(
            self.base_url + '/os-keypairs?limit=3&marker=fake_marker',
            version="2.30", use_admin_context=True)

        self.controller.index(req)

        mock_kp_get.assert_called_once_with(
            req.environ['nova.context'], 'fake_user',
            limit=None, marker=None)


class KeypairsTestV275(test.TestCase):
    def setUp(self):
        super(KeypairsTestV275, self).setUp()
        self.controller = keypairs_v21.KeypairController()

    @mock.patch('nova.objects.KeyPair.get_by_name')
    def test_keypair_list_additional_param_old_version(self, mock_get_by_name):
        req = fakes.HTTPRequest.blank(
            '/os-keypairs?unknown=3',
            version='2.74', use_admin_context=True)
        self.controller.index(req)
        self.controller.show(req, 1)
        with mock.patch.object(self.controller.api, 'delete_key_pair'):
            self.controller.delete(req, 1)

    def test_keypair_list_additional_param(self):
        req = fakes.HTTPRequest.blank(
            '/os-keypairs?unknown=3',
            version='2.75', use_admin_context=True)
        self.assertRaises(exception.ValidationError, self.controller.index,
                          req)

    def test_keypair_show_additional_param(self):
        req = fakes.HTTPRequest.blank(
            '/os-keypairs?unknown=3',
            version='2.75', use_admin_context=True)
        self.assertRaises(exception.ValidationError, self.controller.show,
                          req, 1)

    def test_keypair_delete_additional_param(self):
        req = fakes.HTTPRequest.blank(
            '/os-keypairs?unknown=3',
            version='2.75', use_admin_context=True)
        self.assertRaises(exception.ValidationError, self.controller.delete,
                          req, 1)
